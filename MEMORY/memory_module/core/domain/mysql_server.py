import asyncio
from ulid import ulid
import inspect
import json
import time
from typing import Callable, Dict
import aiomysql
from aiomysql.cursors import DictCursor
from fastapi.encoders import jsonable_encoder

from global_config import MYSQL_DOCKER_BASE_URL, MYSQL_DOCKER_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE, MYSQL_CHARSET, AUTO_COMMIT
from public import TASK_RUNNING_STATUS, TASK_FINISHING_STATUS
from core.commons.logger import logger
from core.commons.decorator import task_handler
from core.commons.type_def import BasicInfo, MessageDict, TaskInfo
from core.commons.id_generator import idgen
from core.domain.model.longterm_memory_helper import LongtermMemoryMessage, memory_model


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
                    logger.info(f"[MysqlService][_call_procedure] append rows: {rows}")
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

    @task_handler("mysql.user.ensure_user_exists")
    async def ensure_user_exists(self, payload: dict) -> dict:
        """
        Ensure user account exists. Call procedure ensure_user_exists.
        If user not exist, raise RuntimeError.

        Args:
            payload: Dict, the format is {
                "client_id": "{{ cid }} : to indicate which user the data is from.",
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or "success",
            }
        """
        logger.info(f"[MysqlService][ensure_user_exists] enter.")
        try:
            user_uid = payload["client_id"]
            res = await self._call_procedure("ensure_user_exists", (user_uid,))
            if(len(res) == 0): raise RuntimeError("[MysqlService][ensure_user_exists] User do not exist.")
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
                "session_id": "{{ sid }} : to indicate which tab the data belong to",
                "title": "conversation title",
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
            conversation_uid = self._conversation_id_generator()
            session_id = payload.get("session_id", "")
            title = payload.get("title", "新的聊天...")

            await self._call_procedure("create_conversation", (user_uid, conversation_uid, title, session_id))
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
                "title": "conversation title",
                "is_pinned": bool,
                "is_deleted": bool,
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
            title = payload.get("title", None)
            pinned = bool(payload.get("is_pinned", None))
            is_deleted = bool(payload.get("is_deleted", None))
            await self._call_procedure("update_conversation", (user_uid, conversation_uid, title, session_id, pinned, is_deleted))
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
                
            result = await self._call_procedure("append_message", (user_uid, conversation_id, role, content, think, extra, info, generation_id, node_id, parent_id, timestamp))
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
                "messages": [  # list of message generation_id and role
                    {
                        "generation_id": str,
                        "role": str # ai or human
                    }
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
            for msg in messages:
                role = msg["role"]
                if role not in ("ai", "human"):
                    continue
                generation_id = msg["generation_id"]
                res = await self._call_procedure("delete_messages", (user_uid, conversation_id, generation_id, role))
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
            rows = await self._call_procedure("insert_file_info", (file_id, file_name, file_path, mime_type, user_uid, conversation_uid))
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
    # Tasks 
    # --------------------------------------------------

    @task_handler("mysql.task.create_task_record")
    async def create_task_record(self, payload: dict) -> dict:
        """
        Store finished task record in MySQL. Call procedure create_task_record.

        Args:
            payload: Dict, the format is {
                "task_id": "{{ tid }} : to identify task",
                "client_id": "{{ cid }} : to indicate which user the data is from.",
                "history_id": "{{ hid }} : Optional",
                "payload": {...}, // dict to store task info, such as task name, params, config dict(model and model_provider) etc.
                "created_at": "",
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or "success",
            }
        """
        logger.info(f"[MysqlService][create_task_record] enter.")
        try:
            task_id = payload["task_id"]
            user_uid = payload["client_id"]
            conversation_uid = payload["history_id"]
            task_payload = payload.get("payload", {})
            created_at = payload.get("created_at", time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))

            if task_payload is None:
                task_payload = {}
            if not isinstance(task_payload, str):
                task_payload = json.dumps(task_payload, ensure_ascii=False)

            await self._call_procedure("create_task_record",(task_id, user_uid, conversation_uid, task_payload, created_at))

            return {
                "success": True,
                "messages": "success",
            }
        except Exception as e:
            logger.exception(f"[MysqlService][create_task_record] ❌ Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("mysql.task.update_task_result")
    async def update_task_result(self, payload: dict) -> dict:
        """
        Store finished task record in MySQL. Call procedure update_task_result.

        Args:
            payload: Dict, the format is {
                "task_id": "{{ tid }} : to identify task",
                "status": "done/failed",
                "result": [...], // the result set of the task.
                "finished_at": "",
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or "success",
            }
        """
        logger.info(f"[MysqlService][update_task_result] enter.")
        try:
            task_id = payload["task_id"]
            status = payload["status"]
            result = payload.get("result", [])
            finished_at = payload.get("finished_at", time.strftime('%Y-%m-%d %H:%M:%S', time.localtime()))
            
            if result is None:
                result = []
            if not isinstance(result, str):
                result = json.dumps(result, ensure_ascii=False)

            rows = await self._call_procedure("update_task_result",(task_id, status, result, finished_at))
            task_info = rows[0] if rows else {} # Have limit 1 in SP
            return {
                "success": True,
                "messages": task_info,
            }
        except Exception as e:
            logger.exception(f"[MysqlService][update_task_result] ❌ Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("mysql.task.fetch_task_info")
    async def fetch_task_info(self, payload: dict) -> dict:
        """
        Fetch target task info from MySQL. Call procedure fetch_task_info.

        Args:
            payload: Dict, the format is {
                "task_id": "{{ tid }} : to identify task",
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or {...} (task info dict),
            }
        """
        logger.info(f"[MysqlService][fetch_task_info] enter.")
        try:            
            task_id = payload["task_id"]

            rows = await self._call_procedure("fetch_task_info", (task_id,))
            task_info = rows[0] if rows else {} # Have limit 1 in SP
            return {
                "success": True,
                "messages": task_info,
            }
        except Exception as e:
            logger.exception(f"[MysqlService][fetch_task_info] ❌ Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("mysql.task.fetch_batches_task_info")
    async def fetch_batches_task_info(self, payload: dict) -> dict:
        """
        Fetch task info in whole conversation from MySQL. Call procedure fetch_batches_task_info.

        Args:
            payload: Dict, the format is {
                "client_id": "{{ tid }} : to identify task",
                "history_id": "{{ tid }} : to identify task",
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or {...} (task info dict),
            }
        """
        logger.info(f"[MysqlService][fetch_batches_task_info] enter.")
        try:            
            user_uid = payload["client_id"]
            conversation_id = payload["history_id"]

            rows = await self._call_procedure("fetch_batches_task_info", (user_uid, conversation_id))
            return {
                "success": True,
                "messages": rows,
            }
        except Exception as e:
            logger.exception(f"[MysqlService][fetch_batches_task_info] ❌ Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    # --------------------------------------------------
    # Longterm Memory 
    # --------------------------------------------------

    @task_handler("mysql.memo.fetch_longterm_memory")
    async def fetch_longterm_memory(self, payload: dict) -> dict:
        """
        Get a batch of memories. Call procedure fetch_longterm_memory.

        Args:
            payload: Dict, the format is {
                "client_id": "{{ cid }} : to indicate which user the data is from.",
                "count": int, // max number of messages to fetch
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
                    "memory_type": str,
                    "content": str,
                    "confidence": float,
                    "created_at": str,
                    "updated_at": str,
                },
                ...
            ]
        """
        logger.info(f"[MysqlService][fetch_longterm_memory] enter.")
        try:
            user_uid = payload["client_id"]
            count = payload.get("count", 15)
            rows = await self._call_procedure("fetch_longterm_memory", (user_uid, count))
            return {
                "success": True,
                "messages": rows,
            }
        except Exception as e:
            logger.exception(f"[MysqlService][fetch_longterm_memory] ❌ Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("mysql.memo.update_longterm_memory")
    async def update_longterm_memory(self, payload: dict) -> dict:
        """
        Get a batch of memories. Call procedure update_longterm_memory.

        Args:
            payload: Dict, the format is 
            {
                "client_id": str,
                "messages": [  # list of update dicts
                    {
                        "action": 'insert', 'modify', 'deprecate', 'refresh',
                        "type": 'transient', 'event', 'rule', 'fact', 'preference',
                        "worth": float,
                        "confidence": float,
                        "content": str,
                        "target_id": ulid, // optional, only uesd when action is modify and deprecate
                        "reason": str, // optional, only uesd when action is deprecate
                    },
                    ...
                ]
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or "success",
                "inserted": int,
                "modified": int,
                "deprecated": int,
            }
        """
        logger.info("[MysqlService][update_longterm_memory] enter.")

        try:
            inserted_item_num = modified_item_num = deprecated_item_num = refreshed_item_num = 0
            user_uid = payload["client_id"]
            messages = payload["messages"]
            now_us = int(time.time() * 1_000_000)
            now_s = now_us / 1_000_000.0

            for memory_item in messages:
                action = memory_item.get("action")
                if not action:
                    continue
                confidence = float(memory_item.get("confidence", 0.0))
                if confidence < 0.7:
                    continue

                # INSERT
                if action == "insert":
                    content = memory_item.get("content", "")
                    worth = float(memory_item.get("worth", 0.0))
                    memo_type = memory_item.get("type", "")

                    if not content or worth < 0.6 or not memo_type:
                        continue

                    memory_id = str(ulid())

                    # Treat insert as an implicit first use
                    memory: LongtermMemoryMessage = {
                        "memory_type": memo_type,
                        "confidence": confidence,
                        "worth": worth,
                        "timestamp": now_us,        # created_timestamp
                        "used_count": 1,            # implicit first use
                        "last_modify_at": now_us,   # same as created
                        "score": None,
                    }

                    score = memory_model.calc_score(memory, now=now_s)

                    await self._call_procedure(
                        "insert_longterm_memory",
                        (
                            memory_id,
                            user_uid,
                            memo_type,
                            content,
                            confidence,
                            worth,
                            now_us,
                            score,
                        ),
                    )
                    inserted_item_num += 1

                # MODIFY
                elif action == "modify":
                    memory_id = memory_item.get("target_id")
                    memo_type = memory_item.get("type", "")
                    content = memory_item.get("content", "")
                    worth = float(memory_item.get("worth", 0.0))

                    if not memory_id or not content or not memo_type:
                        continue

                    # Fetch current memory for re-score
                    rows = await self._call_procedure(
                        "fetch_longterm_memory_for_calc_score",
                        (memory_id, user_uid),
                    )
                    if not rows:
                        continue

                    row = rows[0]
                    memory: LongtermMemoryMessage = {
                        "memory_type": memo_type,
                        "confidence": confidence,
                        "worth": worth,
                        "timestamp": row["created_timestamp"],
                        "used_count": row["used_count"],
                        "last_modify_at": row["updated_timestamp"],
                        "score": None,
                    }

                    score = memory_model.calc_score(memory, now=now_s)

                    await self._call_procedure(
                        "modify_longterm_memory",
                        (
                            memory_id,
                            user_uid,
                            memo_type,
                            content,
                            confidence,
                            worth,
                            now_us,
                            score,
                        ),
                    )
                    modified_item_num += 1

                # DEPRECATE
                elif action == "deprecate":
                    memory_id = memory_item.get("target_id")
                    reason = memory_item.get("reason", "")

                    if not memory_id:
                        continue

                    await self._call_procedure(
                        "deprecate_longterm_memory",
                        (
                            memory_id,
                            user_uid,
                            confidence,
                            reason,
                            now_us,
                        ),
                    )
                    deprecated_item_num += 1

                # REFRESH
                elif action == "refresh":
                    memory_id = memory_item.get("target_id")
                    if not memory_id:
                        continue

                    rows = await self._call_procedure(
                        "fetch_longterm_memory_for_calc_score",
                        (memory_id, user_uid),
                    )
                    if not rows:
                        continue

                    row = rows[0]

                    memory: LongtermMemoryMessage = {
                        "memory_type": row["memory_type"],
                        "confidence": row["confidence"],
                        "worth": row["worth"],
                        "timestamp": row["created_timestamp"],
                        "used_count": row["used_count"]+1,
                        "last_modify_at": row["updated_timestamp"],
                        "score": None,
                    }

                    score = memory_model.calc_score(memory, now=now_s)

                    await self._call_procedure(
                        "refresh_longterm_memory",
                        (
                            memory_id,
                            user_uid,
                            now_us,
                            score,
                        ),
                    )
                    refreshed_item_num += 1

                else:
                    logger.error(f"[MysqlService] Unknown action: {action}")

            return {
                "success": True,
                "messages": {
                    "inserted": inserted_item_num,
                    "modified": modified_item_num,
                    "deprecated": deprecated_item_num,
                    "refreshed": refreshed_item_num,
                }
            }

        except Exception as e:
            logger.exception(
                f"[MysqlService][update_longterm_memory] ❌ {type(e).__name__}: {e}"
            )
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



mysql_server = MysqlService(
    host=MYSQL_DOCKER_BASE_URL,
    port=MYSQL_DOCKER_PORT,
    user=MYSQL_USER,
    password=MYSQL_PASSWORD,
    database=MYSQL_DATABASE,
    charset=MYSQL_CHARSET,
)