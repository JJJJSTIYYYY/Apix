import asyncio
import re
from ulid import ulid
import inspect
import json
import time
from typing import Callable, Dict
import aiomysql
from aiomysql.cursors import DictCursor
from fastapi.encoders import jsonable_encoder

from global_config import MYSQL_DOCKER_BASE_URL, MYSQL_DOCKER_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE, MYSQL_CHARSET, AUTO_COMMIT
from core.commons.logger import logger
from core.commons.decorator import task_handler
from core.commons.id_generator import idgen


class MysqlService:
    """
    MySQL service for persistent storage, include task info with status [done | failed] and dialog conversation history.
    """

    def __init__(self, *, host, port, user, password, database, charset="utf8mb4"):
        self._pool = None
        self._pool_args = dict(
            host=host,
            port=port,
            user=user,
            password=password,
            db=database,
            charset=charset,
            autocommit=AUTO_COMMIT,
            cursorclass=DictCursor,
        )
        self._pool_lock = asyncio.Lock()

    async def init(self):
        """Initialize MySQL connection pool."""
        async with self._pool_lock:
            if not self._pool:
                self._pool = await aiomysql.create_pool(**self._pool_args)

    async def _close(self):
        """Close MySQL connection pool."""
        async with self._pool_lock:
            if self._pool:
                self._pool.close()
                await self._pool.wait_closed()
                self._pool = None

    def _conversation_id_generator(self) -> str:
        """
        Generate a unique conversation ID using Yuki IdGenerator.
        """
        uid = idgen.next_id()
        return str(uid)
    
    async def _call_procedure(self, proc_name: str, params: tuple | None = None):
        """
        Call stored procedure using CALL statement.

        Always return the last result set (may be empty).
        All result sets are fully consumed to keep connection clean.
        """
        logger.info(f"[MysqlService][_call_procedure] enter.")
        if not self._pool:
            raise RuntimeError("[MysqlService][_call_procedure] MySQL pool is not initialized, call init() first")
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cursor:
                if params:
                    placeholders = ", ".join(["%s"] * len(params))
                    sql = f"CALL {proc_name}({placeholders})"
                    await cursor.execute(sql, params)
                else:
                    sql = f"CALL {proc_name}()"
                    await cursor.execute(sql)

                # Only persist the latest message in payload.messages
                # Upstream is responsible for calling append_message per message
                results = []
                while True:
                    rows = await cursor.fetchall()
                    results.append(rows)
                    # logger.info(f"[MysqlService][_call_procedure] append rows: {rows}")
                    if not await cursor.nextset():
                        break
                index = min(len(results), 2) # Ignore Message OK at the fetchall's tail.
                return jsonable_encoder(results[-index]) if results else []
                


    # ------------------------------------------------------------------
    # Handler Export
    # ------------------------------------------------------------------

    def export_handlers(self) -> Dict[str, Callable]:
        handlers: Dict[str, Callable] = {}

        for attr_name in dir(self):
            if attr_name.startswith("_"):
                continue

            attr = getattr(self, attr_name)
            if not callable(attr):
                continue

            task_name = getattr(attr, "_handler_name", None)
            if not task_name:
                continue

            if not inspect.iscoroutinefunction(attr):
                raise TypeError(
                    f"[MysqlService][export_handlers] Task handler '{task_name}' must be async function"
                )

            handlers[task_name] = attr

        return handlers
            
    # --------------------------------------------------
    # Action of Memo Mysql (Dialog Memory)
    # --------------------------------------------------

    @task_handler("mysql.user.create_a_user")
    async def create_a_user(self, payload: dict) -> dict:
        """
        Ensure user account exists. Call procedure create_a_user.
        If user not exist, raise RuntimeError.

        Args:
            payload: Dict, the format is {
                "client_id": str, # user_uid
                "username": str,
                "password": str, # encrypted
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or "success",
            }
        """
        logger.info(f"[MysqlService][create_a_user] enter.")
        try:
            user_uid = payload["client_id"]
            username = payload["username"]
            password = payload["password"]
            await self._call_procedure("create_user", (user_uid, username, password))
            return {
                "success": True,
                "messages": {
                    "msg": "success",
                    "uid": user_uid
                },
            }
        except Exception as e:
            logger.exception(f"[MysqlService][create_a_user] ❌ Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": {
                    "msg": f"{type(e).__name__}: {e}",
                    "uid": None
                },
            }

    @task_handler("mysql.user.verify_user")
    async def verify_user(self, payload: dict) -> dict:
        """
        Ensure user account exists. Call procedure verify_user.
        If user not exist, raise RuntimeError.

        Args:
            payload: Dict, the format is {
                "username": str,
                "password": str, # encrypted
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or "success",
            }
        """
        logger.info(f"[MysqlService][verify_user] enter.")
        try:
            username = payload["username"]
            password = payload["password"]
            res = await self._call_procedure("verify_user", (username, password))
            if(len(res) != 1): raise Exception("User do not exist or wrong password.")
            return {
                "success": True,
                "messages": {
                    "msg": "success",
                    "uid": res[0].get("user_uid")
                },
            }
        except Exception as e:
            logger.exception(f"[MysqlService][verify_user] ❌ Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": {
                    "msg": f"{type(e).__name__}: {e}",
                    "uid": None
                },
            }

    @task_handler("mysql.user.ensure_user_exists")
    async def ensure_user_exists(self, payload: dict, exist: bool = True) -> dict:
        """
        Ensure user account exists. Call procedure ensure_user_exists.
        If user not exist, raise RuntimeError.

        Args:
            payload: Dict, the format is {
                "client_id": "{{ cid }} : to indicate which user the data is from.",
            }
            exist: ensure exist if ture, else ensure not exist.

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or "success",
            }
        """
        logger.info(f"[MysqlService][ensure_user_exists] enter.")
        try:
            user_uid = payload["client_id"]
            user_name = payload.get("username")
            res = await self._call_procedure("ensure_user_exists", (user_uid, user_name))
            # logger.debug(res)
            if exist and len(res) == 0: raise Exception("User do not exist.")
            elif not exist and len(res) > 0: raise Exception("User has already exist.")
            return {
                "success": True,
                "messages": "success",
            }
        except Exception as e:
            logger.exception(f"[MysqlService][ensure_user_exists] ❌ Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    # --------------------------------------------------
    # Action of Memo Mysql (Dialog Memory)
    # --------------------------------------------------

    @task_handler("mysql.memo.fetch_conversation_list")
    async def fetch_conversation_list(self, payload: dict) -> dict:
        """
        Get conversation history list for a user. Call procedure fetch_conversation_list.

        Args:
            payload: Dict, the format is {
                "client_id": "{{ cid }} : to indicate which user the data is from.",
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or [...] (list of conversation histories dicts),
            }
        """
        logger.info(f"[MysqlService][fetch_conversation_list] enter.")
        try:
            user_uid = payload["client_id"]
            logger.info(f"[MysqlService][fetch_conversation_list] user_uid = {user_uid}")
            rows = await self._call_procedure("fetch_conversation_list", (str(user_uid),))
            logger.info(f"[MysqlService][fetch_conversation_list] {rows}")
            return {
                "success": True,
                "messages": rows,
            }
        except Exception as e:
            logger.exception(f"[MysqlService][fetch_conversation_list] ❌ Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("mysql.memo.create_conversation")
    async def create_conversation(self, payload: dict) -> dict:
        """
        Create a new conversation record. Call procedure create_conversation.

        Args:
            payload: Dict, the format is {
                "client_id": "{{ cid }} : to indicate which user the data is from.",
                "platform": str,
                "session_id": "{{ sid }} : to indicate which tab the data belong to",
                "title": "conversation title",
                "workspace": "Agent work dir",
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or "conversation_uid",
            }
        """
        logger.info(f"[MysqlService][create_conversation] enter.")
        try:
            user_uid = payload["client_id"]
            platform = payload.get("platform", "default")
            conversation_uid = self._conversation_id_generator()
            session_id = payload.get("session_id", "")
            title = payload.get("title", "新的聊天...")
            workspace = payload.get("workspace", None)

            await self._call_procedure("create_conversation", (user_uid, platform, conversation_uid, title, workspace, session_id))
            return {
                "success": True,
                "messages": f"{conversation_uid}",
            }
        except Exception as e:
            logger.exception(f"[MysqlService][create_conversation] ❌ Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("mysql.memo.update_conversation")
    async def update_conversation(self, payload: dict) -> dict:
        """
        Update a conversation record. Call procedure update_conversation.

        Args:
            payload: Dict, the format is {
                "client_id": "{{ cid }} : to indicate which user the data is from.",
                "history_id": "{{ hid }} : to indicate which dialog history the data belong to.",
                "session_id": "{{ sid }} : to indicate which tab the data belong to",
                "title": "Conversation title",
                "workspace": "Agent work dir",
                "is_pinned": bool,
                "is_deleted": bool,
                "has_new_message": bool
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or "conversation_uid",
            }
        """
        logger.info(f"[MysqlService][update_conversation] enter.")
        try:
            user_uid = payload["client_id"]
            conversation_uid = payload["history_id"]
            session_id = payload.get("session_id", None)
            workspace = payload.get("workspace", None)
            title = payload.get("title", None)
            pinned = payload.get("is_pinned", None)
            is_deleted = payload.get("is_deleted", None)
            has_new_message = payload.get("has_new_message", None)
            await self._call_procedure(
                "update_conversation", 
                (user_uid, conversation_uid, title, workspace, session_id, pinned, is_deleted, has_new_message)
            )
            return {
                "success": True,
                "messages": f"{conversation_uid}",
            }
        except Exception as e:
            logger.exception(f"[MysqlService][update_conversation] ❌ Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    # --------------------------------------------------
    # Messages
    # --------------------------------------------------

    @task_handler("mysql.memo.append_message")
    async def append_message(self, payload: dict) -> dict:
        """
        Persist a peice of message. Call procedure append_message.
        If len of messages list in payload is over one piece, only append the last one.

        Args:
            payload: Dict, the format is {
                "client_id": "{{ cid }} : to indicate which user the data is from.",
                "history_id": "{{ hid }} : to indicate which dialog history the data belong to.",
                "session_id": "{{ sid }} : to indicate which tab the data belong to",
                "messages": {
                    "role": 'human', 'ai', 'system', 'tool', 'info'
                    "content": "message content",
                    "think": "",
                    "extra": {...},
                    "info": {
                        "model": "...",
                        "total_duration": "...",
                        "model_provider": "...",
                        "total_tokens": int,
                        "id": "",
                    }, 
                    "node_id": str,
                    "parent_id": str,
                    "timestamp": int,
                }
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or dict,
            }
        """
        logger.info(f"[MysqlService][append_message] enter.")
        try:
            user_uid = payload["client_id"]
            conversation_id = payload["history_id"]
            messages = payload["messages"]
            
            if not messages:
                raise ValueError("[MysqlService][append_message] message is empty")
            
            role = messages["role"]
            content = messages["content"]
            think = messages.get("think", "")
            extra = messages.get("extra", {})
            info = messages.get("info", {})
            generation_id = messages.get("generation_id", "")
            node_id = messages.get("node_id", "")
            parent_id = messages.get("parent_id", "")
            timestamp = messages["timestamp"]

            if extra is None:
                extra = {}
            if not isinstance(extra, str):
                extra = json.dumps(extra, ensure_ascii=False)

            if info is None:
                info = {}
            if not isinstance(info, str):
                info = json.dumps(info, ensure_ascii=False)

            if not timestamp:
                raise ValueError("[MysqlService][append_message] message timestamp is empty")
                
            result = await self._call_procedure(
                "append_message", 
                (user_uid, conversation_id, role, content, think, extra, info, generation_id, node_id, parent_id, timestamp)
            )
            cursor =  result[0].get("msg_cursor", -1)
            created_at = result[0].get("created_at")
            if cursor == -1: raise ValueError("Invalid cursor the database returned.")
            return {
                "success": True,
                "messages": {
                    "msg_cursor": cursor,
                    "created_at": created_at
                }
            }
        except Exception as e:
            logger.exception(f"[MysqlService][append_message] ❌ Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("mysql.memo.delete_messages")
    async def delete_messages(self, payload: dict) -> dict:
        """
        Persist a peice of message. Call procedure delete_messages.
        If len of messages list in payload is over one piece, only append the last one.

        Args:
            payload: Dict, the format is {
                "client_id": "{{ cid }} : to indicate which user the data is from.",
                "history_id": "{{ hid }} : to indicate which dialog history the data belong to.",
                "session_id": "{{ sid }} : to indicate which tab the data belong to",
                "messages": [  # list of message node_id
                    str, 
                    ...
                ]
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or list[dict],
            }
        """
        logger.info(f"[MysqlService][delete_messages] enter.")
        try:
            user_uid = payload["client_id"]
            conversation_id = payload["history_id"]
            messages = payload["messages"]
            
            if not messages:
                raise ValueError("[MysqlService][delete_messages] list is empty")
                
            msg_info = []
            for node_id in messages:
                res = await self._call_procedure("delete_messages_node", (user_uid, conversation_id, node_id))
                for row in res:
                    if not isinstance(row, dict):
                        continue
                    raw = row.get("info")
                    if isinstance(raw, str):
                        try:
                            parsed = json.loads(raw)
                        except Exception:
                            continue
                    elif isinstance(raw, dict):
                        parsed = raw
                    else:
                        continue

                    msg_info.append(parsed)
            
            return {
                "success": True,
                "messages": msg_info
            }
        except Exception as e:
            logger.exception(f"[MysqlService][delete_messages] ❌ Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("mysql.memo.fetch_messages_after_cursor")
    async def fetch_messages_after_cursor(self, payload: dict) -> dict:
        """
        Get a batch of messages after cursor (include this cursor). Call procedure fetch_messages_after_cursor.

        Args:
            payload: Dict, the format is {
                "client_id": "{{ cid }} : to indicate which user the data is from.",
                "history_id": "{{ hid }} : to indicate which dialog history the data belong to.",
                "session_id": "{{ sid }} : to indicate which tab the data belong to",
                "cursor": int, // fetch messages with msg_cursor >= after_cursor
                "limit": int, // max number of messages to fetch
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or [...] (list of message dicts),
                "next_cursor": new cursor = latest_msg_cursor + 1.
            }
        """
        logger.info(f"[MysqlService][fetch_messages_after_cursor] enter.")
        try:
            user_uid = payload["client_id"]
            conversation_id = payload["history_id"]
            after_cursor = payload.get("cursor", 0)
            after_cursor = max(int(after_cursor), 0)
            limit = payload.get("limit", 65535)
            rows = await self._call_procedure("fetch_messages_after_cursor", (user_uid, conversation_id, after_cursor, limit))
            next_cursor = rows[-1].get('msg_cursor') + 1 if rows else after_cursor
            return {
                "success": True,
                "messages": rows,
                "next_cursor": next_cursor
            }
        except Exception as e:
            logger.exception(f"[MysqlService][fetch_messages_after_cursor] ❌ Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("mysql.memo.fetch_messages_for_user")
    async def fetch_messages_for_user(self, payload: dict) -> dict:
        """
        Get all messages in one conversation. Call procedure fetch_messages_for_user.

        Args:
            payload: Dict, the format is {
                "client_id": "{{ cid }} : to indicate which user the data is from.",
                "history_id": "{{ hid }} : to indicate which dialog history the data belong to.",
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or [...] (list of message dicts),
            }
        """
        logger.info(f"[MysqlService][fetch_messages_for_user] enter.")
        try:
            user_uid = payload["client_id"]
            conversation_id = payload["history_id"]
            rows = await self._call_procedure("fetch_messages_for_user", (user_uid, conversation_id))
            return {
                "success": True,
                "messages": rows,
            }
        except Exception as e:
            logger.exception(f"[MysqlService][fetch_messages_for_user] ❌ Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    @task_handler("mysql.memo.search_messages_by_keyword")
    async def search_messages_by_keyword(self, payload: dict) -> dict:
        """
        Search messages in all conversations. Call procedure search_messages_by_keyword.

        Args:
            payload: Dict, the format is {
                "client_id": str,
                "keyword": str
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or [...] (list of result dicts),
            }

            Result dict format: {
                "conversation_uid": str,
                "generation_id": str,
                "role": str,
                "content": str,
                "title": str,
                "last_active_at": str
            }
        """
        logger.info("[MysqlService][search_messages_by_keyword] enter.")
        try:
            user_uid = payload["client_id"]
            keyword: str = payload["keyword"]

            # Ignore keywords that contain only %, _, \ and whitespace
            if not re.sub(r"[%_\\\s]+", "", keyword):
                return {
                    "success": True,
                    "messages": [],
                }

            # Normalize separators for SQL LIKE search
            keyword = re.sub(r"[_\\\s]+", "%", keyword)
            keyword = re.sub(r"%+", "%", keyword).strip("%")

            rows = await self._call_procedure("search_messages_by_keyword", (user_uid, keyword))

            return {
                "success": True,
                "messages": rows,
            }

        except Exception as e:
            logger.exception(
                f"[MysqlService][search_messages_by_keyword] ❌ Error: {type(e).__name__}: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    # --------------------------------------------------
    # Files
    # --------------------------------------------------
    @task_handler("mysql.file.insert_file_info")
    async def insert_file_info(self, payload: dict) -> dict:
        """
        Insert one file's info uploaded by user. Call procedure insert_file_info.

        Args:
            payload: Dict, the format is {
                "client_id": "{{ cid }} : to indicate which user the data is from.",
                "history_id": "{{ hid }} : Optional",
                "file_id": "Unique id for each file, Generated by file service.",
                "file_name": "File name user upload.",
                "file_path": "File store path in file service.",
                "mime_type": "File mime type such as pic, doc, txt...",
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or [...] (lists of files dict),
            }
        """
        logger.info(f"[MysqlService][insert_file_info] enter.")
        try:
            file_id = payload["file_id"]
            file_name = payload["file_name"]
            file_path = payload["file_path"]
            mime_type = payload.get("mime_type", '')
            user_uid = payload["client_id"]
            conversation_uid = payload.get("history_id", '')
            rows = await self._call_procedure(
                "insert_file_info", 
                (file_id, file_name, file_path, mime_type, user_uid, conversation_uid)
            )
            return {
                "success": True,
                "messages": rows,
            }
        except Exception as e:
            logger.exception(f"[MysqlService][insert_file_info] ❌ Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    @task_handler("mysql.file.update_file_info")
    async def update_file_info(self, payload: dict) -> dict:
        """
        Update one file's info uploaded by user. Call procedure update_file_info.
        This method is only used to update delete mark at now. 

        Args:
            payload: Dict, the format is {
                "client_id": "{{ cid }} : to indicate which user the data is from.",
                "file_id": "Unique id for each file, Generated by file service.", 
                "is_deleted": bool,
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or [...] (lists of files dict),
            }
        """
        logger.info(f"[MysqlService][update_file_info] enter.")
        try:
            user_uid = payload["client_id"]
            file_id = payload.get("file_id")
            is_deleted = payload.get("is_deleted")
            rows = await self._call_procedure("update_file_info", (file_id, user_uid, is_deleted))
            return {
                "success": True,
                "messages": rows,
            }
        except Exception as e:
            logger.exception(f"[MysqlService][update_file_info] ❌ Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    @task_handler("mysql.file.fetch_recent_files")
    async def fetch_recent_files(self, payload: dict) -> dict:
        """
        Get a batch of recent files user upload. Call procedure fetch_recent_files.

        Args:
            payload: Dict, the format is {
                "client_id": "{{ cid }} : to indicate which user the data is from.",
                "limit": int, // max number of messages to fetch
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or [...] (lists of files dict),
            }
        """
        logger.info(f"[MysqlService][fetch_recent_files] enter.")
        try:
            user_uid = payload["client_id"]
            limit = payload.get("limit", 10)
            rows = await self._call_procedure("fetch_recent_files", (user_uid, limit))
            return {
                "success": True,
                "messages": rows,
            }
        except Exception as e:
            logger.exception(f"[MysqlService][fetch_recent_files] ❌ Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    # --------------------------------------------------
    # Short-term Memory 
    # --------------------------------------------------

    @task_handler("mysql.memo.fetch_shortterm_memory")
    async def fetch_shortterm_memory(self, payload: dict) -> dict:
        """
        Get a batch of memories. Call procedure fetch_shortterm_memory.

        Args:
            payload: Dict, the format is {
                "client_id": "{{ cid }} : to indicate which user the data is from.",
                "history_id": "{{ hid }} : to indicate which dialog history the data belong to.",
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or [...] (list of message dicts),
            }

        NOTE:
        message dicts format:
            "messages": [
                {
                    "memory_id": str,
                    "content": str,
                    "created_timestamp": int,
                }
            ]
        """
        logger.info(f"[MysqlService][fetch_shortterm_memory] enter.")
        try:
            user_uid = payload["client_id"]
            conversation_uid = payload["history_id"]
            rows = await self._call_procedure("fetch_shortterm_memory", (user_uid, conversation_uid))
            return {
                "success": True,
                "messages": rows,
            }
        except Exception as e:
            logger.exception(f"[MysqlService][fetch_shortterm_memory] ❌ Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("mysql.memo.insert_shortterm_memory")
    async def insert_shortterm_memory(self, payload: dict) -> dict:
        """
        Get a batch of memories. Call procedure insert_shortterm_memory.

        Args:
            payload: Dict, the format is {
                "memory_id": str, // Message's id generated by langChain (task_id in tool massage or id in ai message)
                "client_id": "{{ cid }} : to indicate which user the data is from.",,
                "history_id": "{{ hid }} : to indicate which dialog history the data belong to.",
                "content": str,
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or "success",
            }
        """
        logger.info(f"[MysqlService][insert_shortterm_memory] enter.")
        try:
            memory_id = payload["memory_id"]
            user_uid = payload["client_id"]
            conversation_uid = payload["history_id"]
            content = payload["content"]
            created_timestamp = int(time.time() * 1_000_000)
            await self._call_procedure("insert_shortterm_memory", (memory_id, user_uid, conversation_uid, content, created_timestamp))
            return {
                "success": True,
                "messages": "success",
            }
        except Exception as e:
            logger.exception(f"[MysqlService][insert_shortterm_memory] ❌ Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("mysql.memo.delete_shortterm_memory")
    async def delete_shortterm_memory(self, payload: dict) -> dict:
        """
        Get a batch of memories. Call procedure delete_shortterm_memory.

        Args:
            payload: Dict, the format is {
                "memory_ids": list[str], // Message's id generated by langChain (task_id in tool massage or id in ai message)
                "client_id": "{{ cid }} : to indicate which user the data is from.",,
                "history_id": "{{ hid }} : to indicate which dialog history the data belong to.",
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or "success",
            }
        """
        logger.info(f"[MysqlService][delete_shortterm_memory] enter.")
        try:
            memory_id = payload["memory_id"]
            user_uid = payload["client_id"]
            conversation_uid = payload["history_id"]
            await self._call_procedure("delete_shortterm_memory", (json.dumps(memory_id), user_uid, conversation_uid))
            return {
                "success": True,
                "messages": "success",
            }
        except Exception as e:
            logger.exception(f"[MysqlService][delete_shortterm_memory] ❌ Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    # --------------------------------------------------
    # Custom Provider 
    # --------------------------------------------------

    @task_handler("mysql.provider.create_llm_provider")
    async def create_llm_provider(self, payload: dict) -> dict:
        """
        Insert a llm provider meta in database. Call procedure create_llm_provider.

        Args:
            payload: Dict, the format is {
                "provider_id": str, # provider's unique id (uuid4)
                "client_id": str, # to indicate which user the data is from
                "provider_name": str, # provider's name, not null
                "type": str, # provider's protocol, default openai
                "endpoint": str, # provider's endpoint, not null
                "model_list": str, # provider's model list, not null
                "description": str, # description for provider, default null
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or dict {"provider_id": str},
            }
        """
        logger.info(f"[MysqlService][create_llm_provider] enter.")
        try:
            provider_id = payload["provider_id"]
            user_uid = payload["client_id"]
            provider_name = payload["provider_name"]
            provider_type = (payload.get("type", "openai") or "openai").lower()
            endpoint = payload["endpoint"]
            model_list = payload["model_list"]
            description = payload.get("description")
            await self._call_procedure(
                "create_llm_provider", 
                (provider_id, user_uid, provider_name, provider_type, endpoint, json.dumps(model_list), description)
            )
            return {
                "success": True,
                "messages": {
                    "provider_id": provider_id
                },
            }
        except Exception as e:
            logger.exception(f"[MysqlService][create_llm_provider] ❌ Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("mysql.provider.get_llm_providers")
    async def get_llm_providers(self, payload: dict) -> dict:
        """
        Get all llm provider meta in database. Call procedure get_llm_providers.

        Args:
            payload: Dict, the format is {
                "client_id": str, # to indicate which user the request from
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or list [
                    {
                        "provider_id": str,
                        "provider_name": str,
                        "type": str,
                        "endpoint": str,
                        "model_list": list,
                        "description": str,
                        "created_at": str
                    },
                    ...
                ],
            }
        """
        logger.info(f"[MysqlService][get_llm_providers] enter.")
        try:
            user_uid = payload["client_id"]
            rows = await self._call_procedure("get_llm_providers", (user_uid, ))
            return {
                "success": True,
                "messages": rows,
            }
        except Exception as e:
            logger.exception(f"[MysqlService][get_llm_providers] ❌ Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("mysql.provider.get_llm_provider_by_id")
    async def get_llm_provider_by_id(self, payload: dict) -> dict:
        """
        Get a llm provider meta in database. Call procedure get_llm_provider_by_id.

        Args:
            payload: Dict, the format is {
                "provider_id": str, # provider's unique id (uuid4)
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or list [
                    {
                        "provider_id": str,
                        "provider_name": str,
                        "type": str,
                        "endpoint": str,
                        "model_list": list,
                        "description": str,
                        "created_at": str
                    }
                ],
            }
        """
        logger.info(f"[MysqlService][get_llm_provider_by_id] enter.")
        try:
            provider_id = payload["provider_id"]
            rows = await self._call_procedure("get_llm_provider_by_id", (provider_id, ))
            return {
                "success": True,
                "messages": rows,
            }
        except Exception as e:
            logger.exception(f"[MysqlService][get_llm_provider_by_id] ❌ Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("mysql.provider.update_llm_provider")
    async def update_llm_provider(self, payload: dict) -> dict:
        """
        Update a llm provider meta in database, include is_deleted status. Call procedure update_llm_provider.

        Args:
            payload: Dict, the format is {
                "provider_id": str, # provider's unique id (uuid4)
                "client_id": str, # to indicate which user the data is from
                "provider_name": str, # Optional, provider's name
                "type": str, # Optional, provider's protocol
                "endpoint": str, # Optional, provider's endpoint
                "model_list": str, # Optional, provider's model list
                "description": str, # Optional, description for provider
                "is_deleted": bool, # Optional, delete if true
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or "success",
            }
        """
        logger.info(f"[MysqlService][update_llm_provider] enter.")
        try:
            provider_id = payload["provider_id"]
            user_uid = payload["client_id"]
            provider_name = payload.get("provider_name")
            provider_type = payload.get("type")
            if isinstance(provider_type, str):
                provider_type = provider_type.lower()
            endpoint = payload.get("endpoint")
            model_list = payload.get("model_list")
            if isinstance(model_list, list):
                model_list = json.dumps(model_list)
            description = payload.get("description")
            is_deleted = payload.get("is_deleted")
            await self._call_procedure(
                "update_llm_provider", 
                (provider_id, user_uid, provider_name, provider_type, endpoint, model_list, description, is_deleted)
            )
            return {
                "success": True,
                "messages": 'success',
            }
        except Exception as e:
            logger.exception(f"[MysqlService][update_llm_provider] ❌ Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    # --------------------------------------------------
    # MCP Server
    # --------------------------------------------------

    @task_handler("mysql.mcp.create_mcp_server")
    async def create_mcp_server(self, payload: dict) -> dict:
        """
        Insert a mcp server meta in database. Call procedure create_mcp_server.

        Args:
            payload: Dict, the format is {
                "mcp_id": str,
                "client_id": str,
                "mcp_name": str,
                "transport": str,
                "endpoint": str,
                "config": dict,
                "description": str,
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or {
                    "mcp_id": str
                },
            }
        """
        logger.info("[MysqlService][create_mcp_server] enter.")

        try:
            mcp_id = payload["mcp_id"]
            user_uid = payload["client_id"]
            mcp_name = payload["mcp_name"]
            transport = payload["transport"]
            endpoint = payload["endpoint"]
            config = payload.get("config", {})
            description = payload.get("description")

            await self._call_procedure(
                "create_mcp_server",
                (mcp_id, user_uid, mcp_name, transport, endpoint, json.dumps(config), description,),
            )

            return {
                "success": True,
                "messages": {
                    "mcp_id": mcp_id,
                },
            }

        except Exception as e:
            logger.exception(
                f"[MysqlService][create_mcp_server] ❌ Error: {type(e).__name__}: {e}"
            )

            return {
                "success": False,
                "messages": f"fail: {e}",
            }


    @task_handler("mysql.mcp.get_mcp_servers")
    async def get_mcp_servers(self, payload: dict) -> dict:
        """
        Get all mcp servers in database. Call procedure get_mcp_servers.

        Args:
            payload: Dict, the format is {
                "client_id": str,
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": list
            }
        """
        logger.info("[MysqlService][get_mcp_servers] enter.")

        try:
            user_uid = payload["client_id"]

            rows = await self._call_procedure("get_mcp_servers", (user_uid,),)

            return {
                "success": True,
                "messages": rows,
            }

        except Exception as e:
            logger.exception(
                f"[MysqlService][get_mcp_servers] ❌ Error: {type(e).__name__}: {e}"
            )

            return {
                "success": False,
                "messages": f"fail: {e}",
            }


    @task_handler("mysql.mcp.get_enabled_mcp_servers")
    async def get_enabled_mcp_servers(self, payload: dict) -> dict:
        """
        Get enabled mcp servers in database. Call procedure get_enabled_mcp_servers.

        Args:
            payload: Dict, the format is {
                "client_id": str,
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": list
            }
        """
        logger.info("[MysqlService][get_enabled_mcp_servers] enter.")

        try:
            user_uid = payload["client_id"]

            rows = await self._call_procedure("get_enabled_mcp_servers", (user_uid,),)

            return {
                "success": True,
                "messages": rows,
            }

        except Exception as e:
            logger.exception(
                f"[MysqlService][get_enabled_mcp_servers] ❌ Error: {type(e).__name__}: {e}"
            )

            return {
                "success": False,
                "messages": f"fail: {e}",
            }


    @task_handler("mysql.mcp.update_mcp_server")
    async def update_mcp_server(self, payload: dict) -> dict:
        """
        Update a mcp server meta in database. Call procedure update_mcp_server.

        Args:
            payload: Dict, the format is {
                "mcp_id": str,
                "client_id": str,

                "mcp_name": str,
                "transport": str,
                "endpoint": str,
                "config": dict,
                "description": str,

                "enabled": bool,
                "tool_count": int,

                "is_deleted": bool,
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "success"
            }
        """
        logger.info("[MysqlService][update_mcp_server] enter.")

        try:
            mcp_id = payload["mcp_id"]
            user_uid = payload["client_id"]

            mcp_name = payload.get("mcp_name")
            transport = payload.get("transport")
            endpoint = payload.get("endpoint")

            config = payload.get("config")
            if isinstance(config, (dict, list)):
                config = json.dumps(config)

            description = payload.get("description")

            enabled = payload.get("enabled")
            tool_count = payload.get("tool_count")

            is_deleted = payload.get("is_deleted")

            await self._call_procedure(
                "update_mcp_server",
                ( mcp_id, user_uid, mcp_name, transport, endpoint, config, description, enabled, tool_count, is_deleted,),
            )

            return {
                "success": True,
                "messages": "success",
            }

        except Exception as e:
            logger.exception(
                f"[MysqlService][update_mcp_server] ❌ Error: {type(e).__name__}: {e}"
            )

            return {
                "success": False,
                "messages": f"fail: {e}",
            }



mysql_server = MysqlService(
    host=MYSQL_DOCKER_BASE_URL,
    port=MYSQL_DOCKER_PORT,
    user=MYSQL_USER,
    password=MYSQL_PASSWORD,
    database=MYSQL_DATABASE,
    charset=MYSQL_CHARSET,
)