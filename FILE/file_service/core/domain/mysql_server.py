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
from core.commons.logger import logger
from core.commons.decorator import task_handler
from core.commons.type_def import BasicInfo, MessageDict, TaskInfo
from core.commons.id_generator import idgen


class MysqlService:
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
    # Files Not RAG
    # --------------------------------------------------

    @task_handler("mysql.file.insert_file_info")
    async def insert_file_info(self, payload: dict) -> dict:
        """
        Insert uploaded file metadata into MySQL.

        Args:
            payload: Dict, the format is
            {
                "client_id": str,
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
                "success": True / False,
                "messages": "success" or "fail: {e}",
            }
        """
        logger.info("[MysqlService][insert_file_info] enter.")
        try:
            client_id = payload["client_id"]
            file_info_list = payload.get("file_info", [])

            for file_info in file_info_list:
                file_id = file_info["file_id"]
                file_name = file_info["file_name"]
                file_path = file_info["file_path"]
                file_size = file_info["file_size"]
                mime_type = file_info.get("file_type", "unknown")
                sha256 = file_info["sha256"]

                await self._call_procedure("insert_file_info", (file_id, file_name, file_path, file_size, mime_type, client_id, sha256))

            return {
                "success": True,
                "messages": "success",
            }

        except Exception as e:
            logger.exception(
                f"[MysqlService][insert_file_info] ❌ Error: {type(e).__name__}: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

        
    @task_handler("mysql.file.update_file_status")
    async def update_file_status(self, payload: dict) -> dict:
        """
        Update one file's info uploaded by user. Call procedure update_file_status.
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
                "messages": "fail: {e}" or "success",
            }
        """
        logger.info(f"[MysqlService][update_file_status] enter.")
        try:
            user_uid = payload["client_id"]
            file_id = payload.get("file_id")
            is_deleted = payload.get("is_deleted")
            await self._call_procedure("update_file_status", (file_id, user_uid, is_deleted))
            return {
                "success": True,
                "messages": "success",
            }
        except Exception as e:
            logger.exception(f"[MysqlService][update_file_status] ❌ Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    @task_handler("mysql.file.fetch_recent_files")
    async def fetch_recent_files(self, payload: dict) -> dict:
        """
        Get a batch of recent files user upload. Call procedure fetch_recent_files.
        Procedure fetch_recent_files ONLY fetch those files uploaded in recent 5 days and limit 5.

        Args:
            payload: Dict, the format is {
                "client_id": "{{ cid }} : to indicate which user the data is from.",
                "limit": int, // max number of messages to fetch
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or [
                    {
                        "file_id": str,
                        "file_name": str, 
                        "file_path": str, // Relative path based on the current runtime working directory.
                        "upload_at": str,
                        "file_size": int,   # e.g. 123456 (bytes)
                        "sha256": str,
                    },
                    ...
                ] (lists of files dict),
            }
        """
        logger.info(f"[MysqlService][fetch_recent_files] enter.")
        try:
            user_uid = payload["client_id"]
            limit = payload.get("limit", 5)
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
        
    @task_handler("mysql.file.fetch_target_file")
    async def fetch_target_file(self, payload: dict) -> dict:
        """
        Get a specified file. Call procedure fetch_target_file.
        Procedure fetch_target_file ONLY fetch those files uploaded in recent 5 days and limit 5.

        Args:
            payload: Dict, the format is {
                "client_id": "{{ cid }} : to indicate which user the data is from.",
                "file_id": str, 
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or [
                    {
                        "file_id": str,
                        "file_name": str, 
                        "file_path": str, // Relative path based on the current runtime working directory.
                        "upload_at": str,
                        "file_size": int,   # e.g. 123456 (bytes)
                        "mime_type": str,
                        "sha256": str,
                    }
                ] (list of files dict),
            }
        """
        logger.info(f"[MysqlService][fetch_target_file] enter.")
        try:
            user_uid = payload["client_id"]
            file_id = payload.get("file_id")
            rows = await self._call_procedure("fetch_target_file", (user_uid, file_id))
            return {
                "success": True,
                "messages": rows,
            }
        except Exception as e:
            logger.exception(f"[MysqlService][fetch_target_file] ❌ Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    # --------------------------------------------------
    # Agent Skill
    # --------------------------------------------------
    
    @task_handler("mysql.skills.insert_skill_info")
    async def insert_skill_info(self, payload: dict) -> dict:
        """
        Insert uploaded skill metadata into MySQL.

        Args:
            payload: Dict, the format is
            {
                "client_id": str,
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
                "success": True / False,
                "messages": "success" or "fail: {e}",
            }
        """

        logger.info("[MysqlService][insert_skill_info] enter.")
        try:
            user_uid = payload["client_id"]
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
                    (
                        skill_id,
                        skill_name,
                        skill_description,
                        skill_version,
                        package_path,
                        package_size,
                        package_sha256,
                        user_uid,
                    ),
                )

            return {
                "success": True,
                "messages": "success",
            }

        except Exception as e:
            logger.exception(
                f"[MysqlService][insert_skill_info] ❌ Error: {type(e).__name__}: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        

    @task_handler("mysql.skills.update_skill_status")
    async def update_skill_status(self, payload: dict) -> dict:
        """
        Update skill status (activate / deactivate / delete).

        Args:
            payload: Dict, the format is
            {
                "client_id": str,
                "skill_id": str,
                "is_active": bool | None,
                "deleted": bool | None,
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or "success",
            }
        """

        logger.info("[MysqlService][update_skill_status] enter.")

        try:
            user_uid = payload["client_id"]
            skill_id = payload["skill_id"]
            is_active = payload.get("is_active")
            deleted = payload.get("deleted")

            await self._call_procedure(
                "update_agent_skill",
                (
                    skill_id,
                    user_uid,
                    is_active,
                    deleted,
                ),
            )

            return {
                "success": True,
                "messages": "success",
            }

        except Exception as e:
            logger.exception(
                f"[MysqlService][update_skill_status] ❌ Error: {type(e).__name__}: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }


    @task_handler("mysql.skills.fetch_available_skills")
    async def fetch_available_skills(self, payload: dict) -> dict:
        """
        Fetch available skills for user.

        Args:
            payload: Dict, the format is
            {
                "client_id": str,
                "limit": int, // Optional, default 5.
            }

        Return:
            dict, the format is {
                "success": True / False,
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

        logger.info("[MysqlService][fetch_available_skills] enter.")

        try:
            user_uid = payload["client_id"]
            limit = payload.get("limit", 5)

            rows = await self._call_procedure(
                "fetch_agent_skills",
                (user_uid, limit,),
            )

            return {
                "success": True,
                "messages": rows,
            }

        except Exception as e:
            logger.exception(
                f"[MysqlService][fetch_available_skills] ❌ Error: {type(e).__name__}: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }


    @task_handler("mysql.skills.fetch_target_skill")
    async def fetch_target_skill(self, payload: dict) -> dict:
        """
        Fetch target skill for user.

        Args:
            payload: Dict, the format is
            {
                "client_id": str,
                "skill_id": str,
            }

        Return:
            dict, the format is {
                "success": True / False,
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
            user_uid = payload["client_id"]
            skill_id = payload["skill_id"]

            rows = await self._call_procedure(
                "fetch_target_skill",
                (user_uid, skill_id,),
            )

            return {
                "success": True,
                "messages": rows,
            }

        except Exception as e:
            logger.exception(
                f"[MysqlService][fetch_target_skill] ❌ Error: {type(e).__name__}: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    # --------------------------------------------------
    # Rag Document
    # --------------------------------------------------

    @task_handler("mysql.rag.insert_rag_document")
    async def insert_rag_document(self, payload: dict) -> dict:
        """
        Insert uploaded document metadata into MySQL.

        Args:
            payload: Dict, the format is
            {
                "client_id": str,
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
                "success": True / False,
                "messages": "success" or "fail: {e}",
            }
        """
        logger.info("[MysqlService][insert_rag_document] enter.")
        try:
            client_id = payload["client_id"]
            file_info_list = payload.get("file_info", [])

            for file_info in file_info_list:
                file_id = file_info["file_id"]
                file_name = file_info["file_name"]
                file_desc = ""
                mime_type = file_info.get("file_type", "unknown")
                file_path = file_info["file_path"]
                file_size = file_info["file_size"]
                sha256 = file_info["sha256"]

                await self._call_procedure("insert_rag_document", (file_id, file_name, file_desc, mime_type, file_path, file_size, sha256, client_id))

            return {
                "success": True,
                "messages": "success",
            }

        except Exception as e:
            logger.exception(
                f"[MysqlService][insert_rag_document] ❌ Error: {type(e).__name__}: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    @task_handler("mysql.rag.update_document_status")
    async def update_document_status(self, payload: dict) -> dict:
        """
        Update document status (activate / deactivate / delete / embed engine / description).

        Args:
            payload: Dict, the format is
            {
                "client_id": str,
                "document_id": str,
                "description": str | None,
                "embed_engine": list | None,
                "is_active": bool | None,
                "deleted": bool | None,
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or "success",
            }
        """

        logger.info("[MysqlService][update_document_status] enter.")

        try:
            user_uid = payload["client_id"]
            document_id = payload["document_id"]
            description = payload.get("description")
            embed_engine = payload.get("embed_engine")
            is_active = payload.get("is_active")
            deleted = payload.get("deleted")

            if embed_engine is not None and not isinstance(embed_engine, str):
                embed_engine = json.dumps(embed_engine, ensure_ascii=False)

            await self._call_procedure(
                "update_rag_document",
                (
                    document_id,
                    user_uid,
                    is_active,
                    deleted,
                    description,
                    embed_engine,
                ),
            )

            return {
                "success": True,
                "messages": "success",
            }

        except Exception as e:
            logger.exception(
                f"[MysqlService][update_document_status] ❌ Error: {type(e).__name__}: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("mysql.rag.fetch_available_documents")
    async def fetch_available_documents(self, payload: dict) -> dict:
        """
        Fetch uploaded document metadata in MySQL.

        Args:
            payload: Dict, the format is
            {
                "client_id": str,
                "limit": int
            }

        Return:
            dict, the format is {
                "success": True / False,
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
        logger.info("[MysqlService][fetch_available_documents] enter.")
        try:
            client_id = payload["client_id"]
            limit = payload.get("limit", 5)

            rows = await self._call_procedure("fetch_rag_documents", (client_id, limit))

            return {
                "success": True,
                "messages": rows,
            }

        except Exception as e:
            logger.exception(
                f"[MysqlService][fetch_available_documents] ❌ Error: {type(e).__name__}: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("mysql.rag.fetch_target_document")
    async def fetch_target_document(self, payload: dict) -> dict:
        """
        Fetch uploaded document metadata in MySQL.

        Args:
            payload: Dict, the format is
            {
                "client_id": str,
                "document_id": str
            }

        Return:
            dict, the format is {
                "success": True / False,
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
        logger.info("[MysqlService][fetch_target_document] enter.")
        try:
            client_id = payload["client_id"]
            document_id = payload["document_id"]

            rows = await self._call_procedure("fetch_target_document", (client_id, document_id))

            return {
                "success": True,
                "messages": rows,
            }

        except Exception as e:
            logger.exception(
                f"[MysqlService][fetch_target_document] ❌ Error: {type(e).__name__}: {e}"
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