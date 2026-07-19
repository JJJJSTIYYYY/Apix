import asyncio
import re
import json
import time

import aiomysql
from aiomysql.cursors import DictCursor
from fastapi.encoders import jsonable_encoder

from apix.common.lifespan.auto_init import auto_init
from apix.config.base_config import MYSQL_BASE_URL, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE, MYSQL_CHARSET, AUTO_COMMIT
from apix.common.utils.logger import logger
from apix.agent.store.utils.id_generator import idgen


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

    async def start(self):
        """Initialize MySQL connection pool."""
        async with self._pool_lock:
            if not self._pool:
                self._pool = await aiomysql.create_pool(**self._pool_args)

    async def stop(self):
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
        logger.trace()
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
                    if not await cursor.nextset():
                        break
                index = min(len(results), 2) # Ignore Message OK at the fetchall's tail.
                return jsonable_encoder(results[-index]) if results else []
            
    # --------------------------------------------------
    # Action of Memo Mysql (Dialog Memory)
    # --------------------------------------------------

    async def create_a_user(self, payload: dict) -> dict:
        """
        Ensure user account exists. Call procedure create_a_user.
        If user not exist, raise RuntimeError.

        Args:
            payload: Dict, the format is {
                "user_id": str, # user_uid
                "username": str,
                "password": str, # encrypted
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or "success",
            }
        """
        logger.trace()
        try:
            user_uid = payload["user_id"]
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
            logger.exception(f"Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": {
                    "msg": f"{type(e).__name__}: {e}",
                    "uid": None
                },
            }

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
        logger.trace()
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
            logger.exception(f"Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": {
                    "msg": f"{type(e).__name__}: {e}",
                    "uid": None
                },
            }

    async def ensure_user_exists(self, payload: dict, exist: bool = True) -> dict:
        """
        Ensure user account exists. Call procedure ensure_user_exists.
        If user not exist, raise RuntimeError.

        Args:
            payload: Dict, the format is {
                "user_id": user id,
            }
            exist: ensure exist if ture, else ensure not exist.

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or "success",
            }
        """
        logger.trace()
        try:
            user_uid = payload["user_id"]
            user_name = payload.get("username")
            res = await self._call_procedure("ensure_user_exists", (user_uid, user_name))
            if exist and len(res) == 0: raise Exception("User do not exist.")
            elif not exist and len(res) > 0: raise Exception("User has already exist.")
            return {
                "success": True,
                "messages": "success",
            }
        except Exception as e:
            logger.exception(f"Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    # --------------------------------------------------
    # Action of Memo Mysql (Dialog Memory)
    # --------------------------------------------------

    async def fetch_conversation_list(self, payload: dict) -> dict:
        """
        Get conversation history list for a user. Call procedure fetch_conversation_list.

        Args:
            payload: Dict, the format is {
                "user_id": user id,
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or [...] (list of conversation histories dicts),
            }
        """
        logger.trace()
        try:
            user_uid = payload["user_id"]
            rows = await self._call_procedure("fetch_conversation_list", (str(user_uid),))
            return {
                "success": True,
                "messages": rows,
            }
        except Exception as e:
            logger.exception(f"Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    async def get_conversation_meta_by_id(self, payload: dict) -> dict:
        """
        Get a conversation metadata. Call procedure get_conversation_meta_by_id.

        Args:
            payload: Dict, the format is {
                "conversation_id": conversation id,
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or [...] (list of conversation meta dicts),
            }
        """
        logger.trace()
        try:
            conversation_id = payload["conversation_id"]
            rows = await self._call_procedure("get_conversation_meta_by_id", (conversation_id,))
            return {
                "success": True,
                "messages": rows,
            }
        except Exception as e:
            logger.exception(f"Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    async def create_conversation(self, payload: dict) -> dict:
        """
        Create a new conversation record. Call procedure create_conversation.

        Args:
            payload: Dict, the format is {
                "user_id": user id,
                "platform": str,
                "title": "conversation title",
                "workspace": "Agent work dir",
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or "conversation_id",
            }
        """
        logger.trace()
        try:
            user_uid = payload["user_id"]
            platform = payload.get("platform", "default")
            conversation_id = self._conversation_id_generator()
            title = payload.get("title", "新的聊天...")
            workspace = payload.get("workspace", None)
            is_cron = payload.get("is_cron", False)

            await self._call_procedure("create_conversation", (user_uid, platform, conversation_id, title, workspace, is_cron))
            return {
                "success": True,
                "messages": f"{conversation_id}",
            }
        except Exception as e:
            logger.exception(f"Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    async def update_conversation(self, payload: dict) -> dict:
        """
        Update a conversation record. Call procedure update_conversation.

        Args:
            payload: Dict, the format is {
                "user_id": user id,
                "conversation_id": conversation id,
                "title": "Conversation title",
                "workspace": "Agent work dir",
                "is_pinned": bool,
                "is_deleted": bool,
                "has_new_message": bool
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or "conversation_id",
            }
        """
        logger.trace()
        try:
            user_uid = payload["user_id"]
            conversation_id = payload["conversation_id"]
            workspace = payload.get("workspace", None)
            title = payload.get("title", None)
            pinned = payload.get("is_pinned", None)
            is_deleted = payload.get("is_deleted", None)
            has_new_message = payload.get("has_new_message", None)
            await self._call_procedure(
                "update_conversation", 
                (user_uid, conversation_id, title, workspace, pinned, is_deleted, has_new_message)
            )
            return {
                "success": True,
                "messages": f"{conversation_id}",
            }
        except Exception as e:
            logger.exception(f"Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    # --------------------------------------------------
    # Messages
    # --------------------------------------------------

    async def append_message(self, payload: dict) -> dict:
        """
        Persist a peice of message. Call procedure append_message.
        If len of messages list in payload is over one piece, only append the last one.

        Args:
            payload: Dict, the format is {
                "user_id": user id,
                "conversation_id": conversation id,
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
        logger.trace()
        try:
            user_uid = payload["user_id"]
            conversation_id = payload["conversation_id"]
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
            logger.exception(f"Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    async def delete_messages(self, payload: dict) -> dict:
        """
        Persist a peice of message. Call procedure delete_messages.
        If len of messages list in payload is over one piece, only append the last one.

        Args:
            payload: Dict, the format is {
                "user_id": user id,
                "conversation_id": conversation id,
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
        logger.trace()
        try:
            user_uid = payload["user_id"]
            conversation_id = payload["conversation_id"]
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
            logger.exception(f"Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    async def fetch_messages_after_cursor(self, payload: dict) -> dict:
        """
        Get a batch of messages after cursor (include this cursor). Call procedure fetch_messages_after_cursor.

        Args:
            payload: Dict, the format is {
                "user_id": user id,
                "conversation_id": conversation id,
                "cursor": int, # fetch messages with msg_cursor >= after_cursor
                "limit": int, # max number of messages to fetch
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or [...] (list of message dicts),
                "next_cursor": new cursor = latest_msg_cursor + 1.
            }
        """
        logger.trace()
        try:
            user_uid = payload["user_id"]
            conversation_id = payload["conversation_id"]
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
            logger.exception(f"Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    async def fetch_messages_for_user(self, payload: dict) -> dict:
        """
        Get all messages in one conversation. Call procedure fetch_messages_for_user.

        Args:
            payload: Dict, the format is {
                "user_id": user id,
                "conversation_id": conversation id,
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or [...] (list of message dicts),
            }
        """
        logger.trace()
        try:
            user_uid = payload["user_id"]
            conversation_id = payload["conversation_id"]
            rows = await self._call_procedure("fetch_messages_for_user", (user_uid, conversation_id))
            return {
                "success": True,
                "messages": rows,
            }
        except Exception as e:
            logger.exception(f"Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    async def search_messages_by_keyword(self, payload: dict) -> dict:
        """
        Search messages in all conversations. Call procedure search_messages_by_keyword.

        Args:
            payload: Dict, the format is {
                "user_id": str,
                "keyword": str
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or [...] (list of result dicts),
            }

            Result dict format: {
                "conversation_id": str,
                "generation_id": str,
                "role": str,
                "content": str,
                "title": str,
                "last_active_at": str
            }
        """
        logger.trace()
        try:
            user_uid = payload["user_id"]
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
                f"Error: {type(e).__name__}: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    # --------------------------------------------------
    # Files
    # --------------------------------------------------
    async def insert_file_info(self, payload: dict) -> dict:
        """
        Insert one file's info uploaded by user. Call procedure insert_file_info.

        Args:
            payload: Dict, the format is {
                "user_id": user id,
                "conversation_id": conversation id, # Optional
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
        logger.trace()
        try:
            file_id = payload["file_id"]
            file_name = payload["file_name"]
            file_path = payload["file_path"]
            mime_type = payload.get("mime_type", '')
            user_uid = payload["user_id"]
            conversation_id = payload.get("conversation_id", '')
            rows = await self._call_procedure(
                "insert_file_info", 
                (file_id, file_name, file_path, mime_type, user_uid, conversation_id)
            )
            return {
                "success": True,
                "messages": rows,
            }
        except Exception as e:
            logger.exception(f"Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    async def update_file_info(self, payload: dict) -> dict:
        """
        Update one file's info uploaded by user. Call procedure update_file_info.
        This method is only used to update delete mark at now. 

        Args:
            payload: Dict, the format is {
                "user_id": user id,
                "file_id": "Unique id for each file, Generated by file service.", 
                "is_deleted": bool,
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or [...] (lists of files dict),
            }
        """
        logger.trace()
        try:
            user_uid = payload["user_id"]
            file_id = payload.get("file_id")
            is_deleted = payload.get("is_deleted")
            rows = await self._call_procedure("update_file_info", (file_id, user_uid, is_deleted))
            return {
                "success": True,
                "messages": rows,
            }
        except Exception as e:
            logger.exception(f"Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    async def fetch_recent_files(self, payload: dict) -> dict:
        """
        Get a batch of recent files user upload. Call procedure fetch_recent_files.

        Args:
            payload: Dict, the format is {
                "user_id": user id,
                "limit": int, # max number of messages to fetch
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or [...] (lists of files dict),
            }
        """
        logger.trace()
        try:
            user_uid = payload["user_id"]
            limit = payload.get("limit", 10)
            rows = await self._call_procedure("fetch_recent_files", (user_uid, limit))
            return {
                "success": True,
                "messages": rows,
            }
        except Exception as e:
            logger.exception(f"Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    # --------------------------------------------------
    # Short-term Memory 
    # --------------------------------------------------

    async def fetch_shortterm_memory(self, payload: dict) -> dict:
        """
        Get a batch of memories. Call procedure fetch_shortterm_memory.

        Args:
            payload: Dict, the format is {
                "user_id": user id,
                "conversation_id": conversation id,
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
        logger.trace()
        try:
            user_uid = payload["user_id"]
            conversation_id = payload["conversation_id"]
            rows = await self._call_procedure("fetch_shortterm_memory", (user_uid, conversation_id))
            return {
                "success": True,
                "messages": rows,
            }
        except Exception as e:
            logger.exception(f"Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    async def insert_shortterm_memory(self, payload: dict) -> dict:
        """
        Get a batch of memories. Call procedure insert_shortterm_memory.

        Args:
            payload: Dict, the format is {
                "memory_id": str, # Message's id generated by langChain (task_id in tool massage or id in ai message)
                "user_id": user id,,
                "conversation_id": conversation id,
                "content": str,
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or "success",
            }
        """
        logger.trace()
        try:
            memory_id = payload["memory_id"]
            user_uid = payload["user_id"]
            conversation_id = payload["conversation_id"]
            content = payload["content"]
            created_timestamp = int(time.time() * 1_000_000)
            await self._call_procedure("insert_shortterm_memory", (memory_id, user_uid, conversation_id, content, created_timestamp))
            return {
                "success": True,
                "messages": "success",
            }
        except Exception as e:
            logger.exception(f"Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    async def delete_shortterm_memory(self, payload: dict) -> dict:
        """
        Get a batch of memories. Call procedure delete_shortterm_memory.

        Args:
            payload: Dict, the format is {
                "memory_ids": list[str], # Message's id generated by langChain (task_id in tool massage or id in ai message)
                "user_id": user id,,
                "conversation_id": conversation id,
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or "success",
            }
        """
        logger.trace()
        try:
            memory_id = payload["memory_id"]
            user_uid = payload["user_id"]
            conversation_id = payload["conversation_id"]
            await self._call_procedure("delete_shortterm_memory", (json.dumps(memory_id), user_uid, conversation_id))
            return {
                "success": True,
                "messages": "success",
            }
        except Exception as e:
            logger.exception(f"Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    # --------------------------------------------------
    # Custom Provider 
    # --------------------------------------------------

    async def create_llm_provider(self, payload: dict) -> dict:
        """
        Insert a llm provider meta in database. Call procedure create_llm_provider.

        Args:
            payload: Dict, the format is {
                "provider_id": str, # provider's unique id (uuid4)
                "user_id": str, # to indicate which user the data is from
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
        logger.trace()
        try:
            provider_id = payload["provider_id"]
            user_uid = payload["user_id"]
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
            logger.exception(f"Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    async def get_llm_providers(self, payload: dict) -> dict:
        """
        Get all llm provider meta in database. Call procedure get_llm_providers.

        Args:
            payload: Dict, the format is {
                "user_id": str, # to indicate which user the request from
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
        logger.trace()
        try:
            user_uid = payload["user_id"]
            rows = await self._call_procedure("get_llm_providers", (user_uid, ))
            return {
                "success": True,
                "messages": rows,
            }
        except Exception as e:
            logger.exception(f"Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

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
        logger.trace()
        try:
            provider_id = payload["provider_id"]
            rows = await self._call_procedure("get_llm_provider_by_id", (provider_id, ))
            return {
                "success": True,
                "messages": rows,
            }
        except Exception as e:
            logger.exception(f"Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    async def update_llm_provider(self, payload: dict) -> dict:
        """
        Update a llm provider meta in database, include is_deleted status. Call procedure update_llm_provider.

        Args:
            payload: Dict, the format is {
                "provider_id": str, # provider's unique id (uuid4)
                "user_id": str, # to indicate which user the data is from
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
        logger.trace()
        try:
            provider_id = payload["provider_id"]
            user_uid = payload["user_id"]
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
            logger.exception(f"Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    # --------------------------------------------------
    # MCP Server
    # --------------------------------------------------

    async def create_mcp_server(self, payload: dict) -> dict:
        """
        Insert a mcp server meta in database. Call procedure create_mcp_server.

        Args:
            payload: Dict, the format is {
                "mcp_id": str,
                "user_id": str,
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
        logger.trace()

        try:
            mcp_id = payload["mcp_id"]
            user_uid = payload["user_id"]
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
                f"Error: {type(e).__name__}: {e}"
            )

            return {
                "success": False,
                "messages": f"fail: {e}",
            }


    async def get_mcp_servers(self, payload: dict) -> dict:
        """
        Get all mcp servers in database. Call procedure get_mcp_servers.

        Args:
            payload: Dict, the format is {
                "user_id": str,
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or list
            }
        """
        logger.trace()

        try:
            user_uid = payload["user_id"]

            rows = await self._call_procedure("get_mcp_servers", (user_uid,),)

            return {
                "success": True,
                "messages": rows,
            }

        except Exception as e:
            logger.exception(
                f"Error: {type(e).__name__}: {e}"
            )

            return {
                "success": False,
                "messages": f"fail: {e}",
            }


    async def get_enabled_mcp_servers(self, payload: dict) -> dict:
        """
        Get enabled mcp servers in database. Call procedure get_enabled_mcp_servers.

        Args:
            payload: Dict, the format is {
                "user_id": str,
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or list
            }
        """
        logger.trace()

        try:
            user_uid = payload["user_id"]

            rows = await self._call_procedure("get_enabled_mcp_servers", (user_uid,),)

            return {
                "success": True,
                "messages": rows,
            }

        except Exception as e:
            logger.exception(
                f"Error: {type(e).__name__}: {e}"
            )

            return {
                "success": False,
                "messages": f"fail: {e}",
            }


    async def update_mcp_server(self, payload: dict) -> dict:
        """
        Update a mcp server meta in database. Call procedure update_mcp_server.

        Args:
            payload: Dict, the format is {
                "mcp_id": str,
                "user_id": str,

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
                "messages": "success" or "fail: {e}"
            }
        """
        logger.trace()

        try:
            mcp_id = payload["mcp_id"]
            user_uid = payload["user_id"]

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
                f"Error: {type(e).__name__}: {e}"
            )

            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        

    async def create_cron_task(self, payload: dict) -> dict:
        """
        Create a cron task in database. Call procedure create_cron_task.

        Args:
            payload: Dict, the format is {
                "task_id": str,
                "user_id": str,
                "conversation_id": str,
                "platform": str,
                "task_name": str,
                "prompt": str,
                "execute": str,
                "exec_time": str, # ISO-8601
                "repeat": Literal["once", "day", "week", "month", "year"],
                "extra_config": dict,
                "description": str,
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or {
                    "task_id": str
                }
            }
        """
        logger.trace()

        try:
            task_id = payload["task_id"]
            user_uid = payload["user_id"]
            conversation_id = payload.get("conversation_id")
            platform = payload.get("platform")
            task_name = payload.get("task_name")
            task_prompt = payload.get("prompt")
            execute_code = payload.get("execute")
            execute_time = payload.get("exec_time")
            repeat = payload.get("repeat")
            extra_config = payload.get("extra_config", {})
            description = payload.get("description", "")
            
            if extra_config is None:
                extra_config = {}
            if not isinstance(extra_config, str):
                extra_config = json.dumps(extra_config, ensure_ascii=False)

            await self._call_procedure(
                "create_cron_task",
                (task_id, user_uid, conversation_id, platform, task_name, task_prompt, execute_code, execute_time, repeat, extra_config, description,),
            )

            return {
                "success": True,
                "messages": {
                    "task_id": task_id
                },
            }

        except Exception as e:
            logger.exception(
                f"Error: {type(e).__name__}: {e}"
            )

            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        

    async def get_all_enabled_cron_tasks(self, payload: dict) -> dict:
        """
        Get all cron tasks in database. Call procedure get_all_enabled_cron_tasks.

        Args:
            payload: Dict, the format is { }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or list
            }
        """
        logger.trace()

        try:
            rows = await self._call_procedure("get_all_enabled_cron_tasks", (),)

            return {
                "success": True,
                "messages": rows,
            }

        except Exception as e:
            logger.exception(
                f"Error: {type(e).__name__}: {e}"
            )

            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        

    async def get_cron_tasks(self, payload: dict) -> dict:
        """
        Get all cron tasks in database. Call procedure get_cron_tasks.

        Args:
            payload: Dict, the format is {
                "user_id": str,
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or list
            }
        """
        logger.trace()

        try:
            user_uid = payload["user_id"]

            rows = await self._call_procedure("get_cron_tasks", (user_uid,),)

            return {
                "success": True,
                "messages": rows,
            }

        except Exception as e:
            logger.exception(
                f"Error: {type(e).__name__}: {e}"
            )

            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        

    async def get_cron_task_by_id(self, payload: dict) -> dict:
        """
        Get a cron task in database. Call procedure get_cron_task_by_id.

        Args:
            payload: Dict, the format is {
                "task_id": str,
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or list
            }
        """
        logger.trace()

        try:
            task_id = payload["task_id"]

            rows = await self._call_procedure("get_cron_task_by_id", (task_id,),)

            return {
                "success": True,
                "messages": rows,
            }

        except Exception as e:
            logger.exception(
                f"Error: {type(e).__name__}: {e}"
            )

            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    async def update_cron_task(self, payload: dict) -> dict:
        """
        Update a cron task in database. Call procedure update_cron_task.

        Args:
            payload: Dict, the format is {
                "task_id": str,
                "conversation_id": str,
                "platform": str,
                "task_name": str,
                "prompt": str,
                "execute": str,
                "exec_time": str, # ISO-8601
                "repeat": Literal["once", "day", "week", "month", "year"],
                "extra_config": dict,
                "description": str,
                "is_deleted": bool,
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or "success"
            }
        """
        logger.trace()

        try:
            task_id = payload["task_id"]
            conversation_id = payload.get("conversation_id")
            platform = payload.get("platform")
            task_name = payload.get("task_name")
            task_prompt = payload.get("prompt")
            execute_code = payload.get("execute")
            execute_time = payload.get("exec_time")
            repeat = payload.get("repeat")
            extra_config = payload.get("extra_config")
            description = payload.get("description")
            enabled = payload.get("enabled")
            is_deleted = payload.get("is_deleted")

            if isinstance(extra_config, (dict, list)):
                extra_config = json.dumps(extra_config)

            await self._call_procedure(
                "update_cron_task",
                (task_id, conversation_id, platform, task_name, task_prompt, execute_code, execute_time, repeat, extra_config, description, enabled, is_deleted,),
            )

            return {
                "success": True,
                "messages": "success",
            }

        except Exception as e:
            logger.exception(
                f"Error: {type(e).__name__}: {e}"
            )

            return {
                "success": False,
                "messages": f"fail: {e}",
            }



mysql_server = MysqlService(
    host=MYSQL_BASE_URL,
    port=MYSQL_PORT,
    user=MYSQL_USER,
    password=MYSQL_PASSWORD,
    database=MYSQL_DATABASE,
    charset=MYSQL_CHARSET,
)
auto_init.register(mysql_server)