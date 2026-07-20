import asyncio
import re
import json
import time

import aiomysql
from aiomysql.cursors import DictCursor
from fastapi.encoders import jsonable_encoder

from apix.agent.store.core.server.data_store.data_server_base import DataServerBase
from apix.common.lifespan.auto_init import auto_init
from apix.config.base_config import MYSQL_BASE_URL, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE, MYSQL_CHARSET, AUTO_COMMIT
from apix.common.utils.logger import logger


class MysqlService(DataServerBase):
    """
    MySQL service for persistent storage.
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

    
    async def _call_procedure(self, proc_name: str, params: tuple | None = None):
        """
        Call stored procedure using CALL statement.

        Always return the last result set (may be empty).
        All result sets are fully consumed to keep connection clean.
        """
        logger.trace()
        if not self._pool:
            raise RuntimeError("MySQL connection pool is not initialized, call start() first")
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
                "user_uid": str, # user_uid
                "username": str,
                "password": str, # encrypted
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or "success",
            }
        """
        logger.trace()
        try:
            user_uid = payload["user_uid"]
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
                "success": bool,
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
                "user_uid": user id,
            }
            exist: ensure exist if ture, else ensure not exist.

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or "success",
            }
        """
        logger.trace()
        try:
            user_uid = payload["user_uid"]
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
    # Conversation
    # --------------------------------------------------

    async def fetch_conversation_list(self, payload: dict) -> dict:
        """
        Get conversation history list for a user. Call procedure fetch_conversation_list.

        Args:
            payload: Dict, the format is {
                "user_uid": user id,
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or [...] (list of conversation histories dicts),
            }
        """
        logger.trace()
        try:
            user_uid = payload["user_uid"]
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
                "conversation_uid": conversation id,
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or [...] (list of conversation meta dicts),
            }
        """
        logger.trace()
        try:
            conversation_uid = payload["conversation_uid"]
            rows = await self._call_procedure("get_conversation_meta_by_id", (conversation_uid,))
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
                "user_uid": user id,
                "platform": str,
                "title": "conversation title",
                "workspace": "Agent work dir",
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or "conversation_uid",
            }
        """
        logger.trace()
        try:
            user_uid = payload["user_uid"]
            platform = payload.get("platform", "default")
            conversation_uid = self._conversation_id_generator()
            title = payload.get("title", "New Conversation...")
            workspace = payload.get("workspace", None)
            is_cron = payload.get("is_cron", False)

            await self._call_procedure("create_conversation", (user_uid, platform, conversation_uid, title, workspace, is_cron))
            return {
                "success": True,
                "messages": f"{conversation_uid}",
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
                "user_uid": user id,
                "conversation_uid": conversation id,
                "title": "Conversation title",
                "workspace": "Agent work dir",
                "is_pinned": bool,
                "is_deleted": bool,
                "has_new_message": bool
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or "conversation_uid",
            }
        """
        logger.trace()
        try:
            user_uid = payload["user_uid"]
            conversation_uid = payload["conversation_uid"]
            workspace = payload.get("workspace", None)
            title = payload.get("title", None)
            pinned = payload.get("is_pinned", None)
            is_deleted = payload.get("is_deleted", None)
            has_new_message = payload.get("has_new_message", None)
            await self._call_procedure(
                "update_conversation", 
                (user_uid, conversation_uid, title, workspace, pinned, is_deleted, has_new_message)
            )
            return {
                "success": True,
                "messages": f"{conversation_uid}",
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
                "user_uid": user id,
                "conversation_uid": conversation id,
                "messages": {
                    "role": 'user', 'ai', 'system', 'tool', 'info'
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
                "success": bool,
                "messages": "fail: {e}" or dict,
            }
        """
        logger.trace()
        try:
            user_uid = payload["user_uid"]
            conversation_uid = payload["conversation_uid"]
            messages = payload["messages"]
            
            if not messages:
                raise ValueError("Messages list is empty")
            
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
                raise ValueError("Message timestamp is empty")
                
            result = await self._call_procedure(
                "append_message", 
                (user_uid, conversation_uid, role, content, think, extra, info, generation_id, node_id, parent_id, timestamp)
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
                "user_uid": user id,
                "conversation_uid": conversation id,
                "messages": [ 
                    str, 
                    ...
                ] # list of message node_id
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or list[dict],
            }
        """
        logger.trace()
        try:
            user_uid = payload["user_uid"]
            conversation_uid = payload["conversation_uid"]
            messages = payload["messages"]
            
            if not messages:
                raise ValueError("Messages list is empty")
                
            msg_info = []
            for node_id in messages:
                res = await self._call_procedure("delete_messages_node", (user_uid, conversation_uid, node_id))
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
                "user_uid": user id,
                "conversation_uid": conversation id,
                "cursor": int, # fetch messages with msg_cursor >= after_cursor
                "limit": int, # max number of messages to fetch
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or [...] (list of message dicts),
                "next_cursor": new cursor = latest_msg_cursor + 1.
            }
        """
        logger.trace()
        try:
            user_uid = payload["user_uid"]
            conversation_uid = payload["conversation_uid"]
            after_cursor = payload.get("cursor", 0)
            after_cursor = max(int(after_cursor), 0)
            limit = payload.get("limit", 65535)
            rows = await self._call_procedure("fetch_messages_after_cursor", (user_uid, conversation_uid, after_cursor, limit))
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
        
        
    async def search_messages_by_keyword(self, payload: dict) -> dict:
        """
        Search messages in all conversations. Call procedure search_messages_by_keyword.

        Args:
            payload: Dict, the format is {
                "user_uid": str,
                "keyword": str
            }

        Return:
            dict, the format is {
                "success": bool,
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
        logger.trace()
        try:
            user_uid = payload["user_uid"]
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
            logger.exception(f"Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    # --------------------------------------------------
    # Skills (meta only)
    # --------------------------------------------------

    async def insert_skill_info(self, payload: dict) -> dict:
        """
        Insert uploaded skill metadata into MySQL.

        Args:
            payload: Dict, the format is
            {
                "user_uid": str,
                "messages": [
                    {
                        "skill_id": str,
                        "skill_name": str,
                        "skill_description": str,
                        "skill_version": str,
                        "package_path": str,
                        "package_size": int,
                        "package_sha256": str,
                    },
                    ...
                ]
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "success" or "fail: {e}",
            }
        """

        logger.trace()
        try:
            user_uid = payload["user_uid"]
            skill_info_list = payload.get("messages", [])

            for skill in skill_info_list:
                skill_id = skill["skill_id"]
                skill_name = skill["skill_name"]
                skill_description = skill["skill_description"]
                skill_version = skill.get("skill_version", "v1.0")
                package_path = skill["package_path"]
                package_size = skill["package_size"]
                package_sha256 = skill.get("package_sha256")

                await self._call_procedure(
                    "insert_agent_skill",
                    (skill_id, skill_name, skill_description, skill_version, package_path, package_size, package_sha256, user_uid)
                )

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
        

    async def update_skill_status(self, payload: dict) -> dict:
        """
        Update skill status (activate / deactivate / delete).

        Args:
            payload: Dict, the format is
            {
                "user_uid": str,
                "skill_id": str,
                "is_active": bool | None,
                "deleted": bool | None,
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or "success",
            }
        """

        logger.trace()

        try:
            user_uid = payload["user_uid"]
            skill_id = payload["skill_id"]
            is_active = payload.get("is_active")
            deleted = payload.get("deleted")

            await self._call_procedure(
                "update_agent_skill",
                ( skill_id, user_uid, is_active, deleted),
            )

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
        
        
    async def fetch_available_skills(self, payload: dict) -> dict:
        """
        Fetch available skills for user.

        Args:
            payload: Dict, the format is
            {
                "user_uid": str,
                "limit": int, // Optional, default 5.
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": [
                    {
                        "skill_id": str,
                        "skill_name": str,
                        "skill_description": str,
                        "skill_version": str,
                        "package_path": str,
                        "package_size": int,
                        "is_active": bool,
                        "upload_at": str,
                    },
                    ...
                ]
            }
        """

        logger.trace()

        try:
            user_uid = payload["user_uid"]
            limit = payload.get("limit", 5)

            rows = await self._call_procedure("fetch_agent_skills", (user_uid, limit,))

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
        

    async def fetch_target_skill(self, payload: dict) -> dict:
        """
        Fetch target skill for user.

        Args:
            payload: Dict, the format is
            {
                "user_uid": str,
                "skill_id": str,
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": [
                    {
                        "skill_id": str,
                        "skill_name": str,
                        "skill_description": str,
                        "skill_version": str,
                        "package_path": str,
                        "package_size": int,
                        "is_active": bool,
                        "upload_at": str,
                    }
                ]
            }
        """

        logger.info("[MysqlService][fetch_target_skill] enter.")

        try:
            user_uid = payload["user_uid"]
            skill_id = payload["skill_id"]

            rows = await self._call_procedure("fetch_target_skill", (user_uid, skill_id,))

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
    # Rag Document (meta only)
    # --------------------------------------------------

    async def insert_rag_document(self, payload: dict) -> dict:
        """
        Insert uploaded document metadata into MySQL.

        Args:
            payload: Dict, the format is
            {
                "user_uid": str,
                "file_info": [
                    {
                        "file_id": str,
                        "file_name": str,
                        "file_path": str,
                        "file_size": int,   # e.g. 123456 (bytes)
                        "file_type": str,   # e.g. "application/pdf"
                        "sha256": str,
                    },
                    ...
                ]
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "success" or "fail: {e}",
            }
        """
        logger.trace()
        try:
            user_uid = payload["user_uid"]
            file_info_list = payload.get("file_info", [])

            for file_info in file_info_list:
                file_id = file_info["file_id"]
                file_name = file_info["file_name"]
                file_desc = ""
                mime_type = file_info.get("file_type", "unknown")
                file_path = file_info["file_path"]
                file_size = file_info["file_size"]
                sha256 = file_info["sha256"]

                await self._call_procedure(
                    "insert_rag_document", 
                    (file_id, file_name, file_desc, mime_type, file_path, file_size, sha256, user_uid)
                )

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
        

    async def update_document_status(self, payload: dict) -> dict:
        """
        Update document status (activate / deactivate / delete / embed engine / description).

        Args:
            payload: Dict, the format is
            {
                "user_uid": str,
                "document_id": str,
                "description": str | None,
                "embed_engine": list | None,
                "is_active": bool | None,
                "deleted": bool | None,
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or "success",
            }
        """

        logger.trace()

        try:
            user_uid = payload["user_uid"]
            document_id = payload["document_id"]
            description = payload.get("description")
            embed_engine = payload.get("embed_engine")
            is_active = payload.get("is_active")
            deleted = payload.get("deleted")

            if embed_engine is not None and not isinstance(embed_engine, str):
                embed_engine = json.dumps(embed_engine, ensure_ascii=False)

            await self._call_procedure(
                "update_rag_document",
                (document_id, user_uid, is_active, deleted, description, embed_engine),
            )

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


    async def fetch_available_documents(self, payload: dict) -> dict:
        """
        Fetch uploaded document metadata in MySQL.

        Args:
            payload: Dict, the format is
            {
                "user_uid": str,
                "limit": int
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": [
                    {
                        "document_id": str,
                        "document_name": str,
                        "document_description": str,
                        "embed_engine": list,
                        "mime_type": str,
                        "document_path": str,
                        "document_size": int,
                        "document_sha256": str,
                        "is_active": bool,
                        "upload_at": str
                    },
                    ...
                ]
            }
        """
        logger.trace()
        try:
            user_uid = payload["user_uid"]
            limit = payload.get("limit", 5)

            rows = await self._call_procedure("fetch_rag_documents", (user_uid, limit))

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


    async def fetch_target_document(self, payload: dict) -> dict:
        """
        Fetch uploaded document metadata in MySQL.

        Args:
            payload: Dict, the format is
            {
                "user_uid": str,
                "document_id": str
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": [
                    {
                        "document_id": str,
                        "document_name": str,
                        "document_description": str,
                        "embed_engine": list,
                        "mime_type": str,
                        "document_path": str,
                        "document_size": int,
                        "document_sha256": str,
                        "is_active": bool,
                        "deleted": bool,
                        "upload_at": str,
                        "deleted_at": str
                    }
                ]
            }
        """
        logger.trace()
        try:
            user_uid = payload["user_uid"]
            document_id = payload["document_id"]

            rows = await self._call_procedure("fetch_target_document", (user_uid, document_id))

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
                "user_uid": user id,
                "conversation_uid": conversation id,
            }

        Return:
            dict, the format is {
                "success": bool,
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
            user_uid = payload["user_uid"]
            conversation_uid = payload["conversation_uid"]
            rows = await self._call_procedure("fetch_shortterm_memory", (user_uid, conversation_uid))
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
                "user_uid": user id,,
                "conversation_uid": conversation id,
                "content": str,
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or "success",
            }
        """
        logger.trace()
        try:
            memory_id = payload["memory_id"]
            user_uid = payload["user_uid"]
            conversation_uid = payload["conversation_uid"]
            content = payload["content"]
            created_timestamp = int(time.time() * 1_000_000)
            await self._call_procedure("insert_shortterm_memory", (memory_id, user_uid, conversation_uid, content, created_timestamp))
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
                "user_uid": user id,,
                "conversation_uid": conversation id,
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or "success",
            }
        """
        logger.trace()
        try:
            memory_ids = payload["memory_ids"]
            user_uid = payload["user_uid"]
            conversation_uid = payload["conversation_uid"]
            await self._call_procedure("delete_shortterm_memory", (json.dumps(memory_ids), user_uid, conversation_uid))
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
                "user_uid": str, # to indicate which user the data is from
                "provider_name": str, # provider's name, not null
                "type": str, # provider's protocol, default openai
                "endpoint": str, # provider's endpoint, not null
                "model_list": str, # provider's model list, not null
                "description": str, # description for provider, default null
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or dict {"provider_id": str},
            }
        """
        logger.trace()
        try:
            provider_id = payload["provider_id"]
            user_uid = payload["user_uid"]
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
                "user_uid": str, # to indicate which user the request from
            }

        Return:
            dict, the format is {
                "success": bool,
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
            user_uid = payload["user_uid"]
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
                "success": bool,
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
                "user_uid": str, # to indicate which user the data is from
                "provider_name": str, # Optional, provider's name
                "type": str, # Optional, provider's protocol
                "endpoint": str, # Optional, provider's endpoint
                "model_list": str, # Optional, provider's model list
                "description": str, # Optional, description for provider
                "is_deleted": bool, # Optional, delete if true
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or "success",
            }
        """
        logger.trace()
        try:
            provider_id = payload["provider_id"]
            user_uid = payload["user_uid"]
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
                "user_uid": str,
                "mcp_name": str,
                "transport": str,
                "endpoint": str,
                "config": dict,
                "description": str,
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or {
                    "mcp_id": str
                },
            }
        """
        logger.trace()

        try:
            mcp_id = payload["mcp_id"]
            user_uid = payload["user_uid"]
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
            logger.exception(f"Error: {type(e).__name__}: {e}")

            return {
                "success": False,
                "messages": f"fail: {e}",
            }


    async def get_mcp_servers(self, payload: dict) -> dict:
        """
        Get all mcp servers in database. Call procedure get_mcp_servers.

        Args:
            payload: Dict, the format is {
                "user_uid": str,
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or list
            }
        """
        logger.trace()

        try:
            user_uid = payload["user_uid"]

            rows = await self._call_procedure("get_mcp_servers", (user_uid,),)

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


    async def get_enabled_mcp_servers(self, payload: dict) -> dict:
        """
        Get enabled mcp servers in database. Call procedure get_enabled_mcp_servers.

        Args:
            payload: Dict, the format is {
                "user_uid": str,
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or list
            }
        """
        logger.trace()

        try:
            user_uid = payload["user_uid"]

            rows = await self._call_procedure("get_enabled_mcp_servers", (user_uid,),)

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


    async def update_mcp_server(self, payload: dict) -> dict:
        """
        Update a mcp server meta in database. Call procedure update_mcp_server.

        Args:
            payload: Dict, the format is {
                "mcp_id": str,
                "user_uid": str,

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
                "success": bool,
                "messages": "success" or "fail: {e}"
            }
        """
        logger.trace()

        try:
            mcp_id = payload["mcp_id"]
            user_uid = payload["user_uid"]

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
            logger.exception(f"Error: {type(e).__name__}: {e}")

            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    # --------------------------------------------------
    # Cron task
    # --------------------------------------------------

    async def create_cron_task(self, payload: dict) -> dict:
        """
        Create a cron task in database. Call procedure create_cron_task.

        Args:
            payload: Dict, the format is {
                "task_id": str,
                "user_uid": str,
                "conversation_uid": str,
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
                "success": bool,
                "messages": "fail: {e}" or {
                    "task_id": str
                }
            }
        """
        logger.trace()

        try:
            task_id = payload["task_id"]
            user_uid = payload["user_uid"]
            conversation_uid = payload.get("conversation_uid")
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
                (task_id, user_uid, conversation_uid, platform, task_name, task_prompt, execute_code, execute_time, repeat, extra_config, description,),
            )

            return {
                "success": True,
                "messages": {
                    "task_id": task_id
                },
            }

        except Exception as e:
            logger.exception(f"Error: {type(e).__name__}: {e}")

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
                "success": bool,
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
            logger.exception(f"Error: {type(e).__name__}: {e}")

            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        

    async def get_cron_tasks(self, payload: dict) -> dict:
        """
        Get all cron tasks in database. Call procedure get_cron_tasks.

        Args:
            payload: Dict, the format is {
                "user_uid": str,
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or list
            }
        """
        logger.trace()

        try:
            user_uid = payload["user_uid"]

            rows = await self._call_procedure("get_cron_tasks", (user_uid,),)

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
        

    async def get_cron_task_by_id(self, payload: dict) -> dict:
        """
        Get a cron task in database. Call procedure get_cron_task_by_id.

        Args:
            payload: Dict, the format is {
                "task_id": str,
            }

        Return:
            dict, the format is {
                "success": bool,
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
            logger.exception(f"Error: {type(e).__name__}: {e}")

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
                "conversation_uid": str,
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
                "success": bool,
                "messages": "fail: {e}" or "success"
            }
        """
        logger.trace()

        try:
            task_id = payload["task_id"]
            conversation_uid = payload.get("conversation_uid")
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
                (task_id, conversation_uid, platform, task_name, task_prompt, execute_code, execute_time, repeat, extra_config, description, enabled, is_deleted,),
            )

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



data_server = MysqlService(
    host=MYSQL_BASE_URL,
    port=MYSQL_PORT,
    user=MYSQL_USER,
    password=MYSQL_PASSWORD,
    database=MYSQL_DATABASE,
    charset=MYSQL_CHARSET,
)
auto_init.register(data_server)