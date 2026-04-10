from datetime import datetime
import inspect
import json
from typing import Callable, Dict

from core.commons.logger import logger
from core.commons.decorator import task_handler
from core.commons.text_spliter import TextSplitter

from core.domain.mysql_server import MysqlService
from core.domain.milvus_server import MilvusService
from core.domain.file_server import FileService


class DataExecutors:
    """
    Execution layer.
    Responsible for orchestrating service-level atomic operations.
    """

    def __init__(
        self,
        *,
        mysql_store: MysqlService,
        milvus_store: MilvusService,
        file_store: FileService,
    ):
        self.mysql = mysql_store
        self.milvus = milvus_store
        self.file_service = file_store

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
                    f"[DataExecutors][export_handlers] Task handler '{task_name}' must be async function"
                )

            handlers[task_name] = attr

        return handlers

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    @task_handler("ensure_user_exists")
    async def ensure_user_exists(self, payload: dict) -> dict:
        """
        Ensure user exists in persistent storage.

        Workflow:
        - Insert user if not exists
        - Update user info if exists
        """
        try:
            logger.info("[DataExecutors][ensure_user_exists] enter.")
            return await self.mysql.ensure_user_exists(payload)

        except Exception as e:
            logger.exception(
                f"[DataExecutors][ensure_user_exists] error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    # ------------------------------------------------------------------
    # Files (MySQL)
    # ------------------------------------------------------------------

    @task_handler("insert_file")
    async def insert_file(self, payload: dict) -> dict:
        """
        Insert files (non-RAG workflow).

        Workflow:
        - Save uploaded files via FileService
        - Ensure user exists
        - Insert file metadata into MySQL
        """
        try:
            logger.info("[DataExecutors][insert_file] enter.")

            res = await self.mysql.ensure_user_exists(payload)
            if not res.get("success"):
                return res

            file_res = await self.file_service.save_file(payload)
            if not file_res.get("success"):
                return file_res

            mysql_payload = {
                "client_id": payload["client_id"],
                "file_info": file_res.get("messages", []),
            }

            mysql_res = await self.mysql.insert_file_info(mysql_payload)

            if not mysql_res.get("success"):
                return mysql_res

            messages = []
            for row in file_res.get("messages", []):
                file_id = row.get("file_id")
                file_name = row.get("file_name")
                if not file_id or not file_name:
                    continue
                messages.append(
                    {
                        "file_id": file_id,
                        "file_name": file_name,
                    }
                )

            return {
                "success": True,
                "messages": messages,
            }

        except Exception as e:
            logger.exception(
                f"[DataExecutors][insert_file] error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("update_file_status")
    async def update_file_status(self, payload: dict) -> dict:
        """
        Update file info in MySQL.
        Typically used to mark a file as deleted.
        """
        try:
            logger.info("[DataExecutors][update_file_status] enter.")
            return await self.mysql.update_file_status(payload)

        except Exception as e:
            logger.exception(
                f"[DataExecutors][update_file_status] error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("get_recent_files")
    async def get_recent_files(self, payload: dict) -> dict:
        """
        Fetch recent files uploaded by user.

        Mention: This method does not fetch binary.
        """
        try:
            logger.info("[DataExecutors][get_recent_files] enter.")
            return await self.mysql.fetch_recent_files(payload)

        except Exception as e:
            logger.exception(
                f"[DataExecutors][get_recent_files] error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("download_file")
    async def download_file(self, payload: dict) -> dict:
        """
        Fetch target file metadata uploaded by user.

        Mention: This method does not fetch binary.
        """
        try:
            logger.info("[DataExecutors][download_file] enter.")
            return await self.mysql.fetch_target_file(payload)

        except Exception as e:
            logger.exception(
                f"[DataExecutors][download_file] error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    # ------------------------------------------------------------------
    # Skills Files
    # ------------------------------------------------------------------

    @task_handler("insert_skills")
    async def insert_skills(self, payload: dict) -> dict:
        """
        Fetch recent files uploaded by user.

        Mention: This method does not fetch binary.
        """
        try:
            logger.info("[DataExecutors][insert_skills] enter.")

            res = await self.mysql.ensure_user_exists(payload)
            if not res.get("success"):
                return res

            file_res = await self.file_service.handle_skill_package(payload)
            if not file_res.get("success"):
                return file_res

            mysql_res = await self.mysql.insert_skill_info(file_res)
            if not mysql_res.get("success"):
                return mysql_res
            
            skill_info_list = file_res.get("messages", [])
            visible_skill_info_list = []

            for skill_info in skill_info_list:
                visible_skill_info = {
                    "skill_id": skill_info.get('skill_id'),
                    "skill_name": skill_info.get('skill_name'),
                    "skill_description": skill_info.get('skill_description'),
                    "skill_version": skill_info.get('skill_version'),
                    "package_size": skill_info.get('package_size'),
                    "is_active": False,
                    "upload_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                visible_skill_info_list.append(visible_skill_info)

            return {
                "success": True,
                "messages": visible_skill_info_list,
            }

        except Exception as e:
            logger.exception(
                f"[DataExecutors][insert_skills] error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("update_skill")
    async def update_skill(self, payload: dict) -> dict:
        """
        Update skill info in MySQL.
        Typically used to mark a file as deleted or active.
        """
        try:
            logger.info("[DataExecutors][update_skill] enter.")
            return await self.mysql.update_skill_status(payload)

        except Exception as e:
            logger.exception(
                f"[DataExecutors][update_skill] error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("fetch_skills")
    async def fetch_skills(self, payload: dict) -> dict:
        """
        Fetch skills uploaded by user.

        Mention: This method does not fetch binary.
        """
        try:
            logger.info("[DataExecutors][fetch_skills] enter.")
            return await self.mysql.fetch_available_skills(payload)

        except Exception as e:
            logger.exception(
                f"[DataExecutors][fetch_skills] error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("fetch_target_skill")
    async def fetch_target_skill(self, payload: dict) -> dict:
        """
        Fetch target skill uploaded by user.

        Mention: This method does not fetch binary.
        """
        try:
            logger.info("[DataExecutors][fetch_target_skill] enter.")
            return await self.mysql.fetch_target_skill(payload)

        except Exception as e:
            logger.exception(
                f"[DataExecutors][fetch_target_skill] error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    # ------------------------------------------------------------------
    # Documents (RAG) (Milvus)
    # ------------------------------------------------------------------

    @task_handler("insert_document")
    async def insert_document(self, payload: dict) -> dict:
        """
        Insert documents. This method does not embed document.

        Workflow:
        - Save uploaded files via FileService
        - Ensure user exists
        - Insert file metadata into MySQL
        """
        try:
            logger.info("[DataExecutors][insert_document] enter.")

            res = await self.mysql.ensure_user_exists(payload)
            if not res.get("success"):
                return res

            file_res = await self.file_service.save_file(payload)
            if not file_res.get("success"):
                return file_res
            
            filter_res = self.file_service.guard_file_type(file_res.get("messages", []), allow_type=FileService.DOCUMENT_TYPE)

            mysql_payload = {
                "client_id": payload["client_id"],
                "file_info": filter_res.get("messages", []),
            }

            mysql_res = await self.mysql.insert_rag_document(mysql_payload)

            if not mysql_res.get("success"):
                return mysql_res

            messages = []
            for row in filter_res.get("messages", []):
                file_id = row.get("file_id")
                file_name = row.get("file_name")
                if not file_id or not file_name:
                    continue
                messages.append(
                    {
                        "document_id": file_id,
                        "document_name": file_name,
                        "document_size": row.get("file_size"),
                        "mime_type": row.get("file_type", "unknown"),
                        "upload_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                )

            return {
                "success": True,
                "messages": messages,
            }

        except Exception as e:
            logger.exception(
                f"[DataExecutors][insert_document] error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("update_document")
    async def update_document(self, payload: dict) -> dict:
        """
        Update document info in MySQL.
        """
        try:
            logger.info("[DataExecutors][update_document] enter.")
            res = await self.mysql.update_document_status(payload)
            if res.get("success") and payload.get("deleted", False):
                milvus_payload = {
                    "client_id": payload["client_id"],
                    "document_id": payload["document_id"],
                }
                return await self.milvus.delete_file_vectors(milvus_payload)
            return res

        except Exception as e:
            logger.exception(
                f"[DataExecutors][update_document] error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("get_available_documents")
    async def get_available_documents(self, payload: dict) -> dict:
        """
        Get available documents (Not deleted)
        """
        try:
            logger.info("[DataExecutors][get_available_documents] enter.")
            return await self.mysql.fetch_available_documents(payload)

        except Exception as e:
            logger.exception(
                f"[DataExecutors][get_available_documents] error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("get_target_document")
    async def get_target_document(self, payload: dict) -> dict:
        """
        Fetch target document uploaded by user.

        Mention: This method does not fetch binary.
        """
        try:
            logger.info("[DataExecutors][get_target_document] enter.")
            return await self.mysql.fetch_target_document(payload)

        except Exception as e:
            logger.exception(
                f"[DataExecutors][get_target_document] error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("embed_document")
    async def embed_document(self, payload: dict) -> dict:
        """
        Upload file and insert chunks into Milvus.

        Workflow:
        - Get meta from MySQL
        - Split file into chunks
        - Insert chunks into Milvus
        """
        try:
            logger.info("[DataExecutors][embed_document] enter.")

            fetch_res = await self.mysql.fetch_target_document(payload)
            if not fetch_res.get("success") or not fetch_res.get("messages"):
                return fetch_res
            
            document_meta = fetch_res.get("messages")[0]
            embed_engine_list = document_meta.get("embed_engine", []) or []
            if isinstance(embed_engine_list, str):
                embed_engine_list = json.loads(embed_engine_list)
            if payload["selected_embed_model"] in embed_engine_list:
                return {
                    "success": True,
                    "messages": f"Embedding already exists. Skipped.",
                }
            
            splitted_document, split_mode = self.file_service.splitter_document(document_meta.get("document_path"))

            milvus_payload = {
                "client_id": payload["client_id"],
                "document_id": payload["document_id"],
                "provider": "ollama",
                "model": payload["selected_embed_model"],
                "api_key": "",
                "extra_config": None,
                "chunks": splitted_document,
                "split_mode": split_mode,
            }
            milvus_res = await self.milvus.insert_file_chunks(milvus_payload)
            if not milvus_res.get("success"):
                return milvus_res
            
            embed_engine_list.append(payload["selected_embed_model"])
            mysql_payload = {
                "client_id": payload["client_id"],
                "document_id": payload["document_id"],
                "embed_engine": embed_engine_list,
            }
            mysql_res = await self.mysql.update_document_status(mysql_payload)
            if not mysql_res.get("success"):
                res = await self.milvus.delete_file_vectors(milvus_payload)
                if not res.get("success"):
                    raise RuntimeError(mysql_res.get("messages", "") + "Milvus roll back failed: " + res.get("messages", ""))
                return mysql_res

            return milvus_res

        except Exception as e:
            logger.exception(
                f"[DataExecutors][embed_document] error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("vector_search")
    async def vector_search(self, payload: dict) -> dict:
        """
        Perform vector similarity search for RAG.

        Args:
            payload: {
                "client_id": str,
                "document_ids": str | list,
                "provider": str,
                "model": str,
                "api_key": str,
                "query": str,
                "top_k": int,
            }
        """
        try:
            logger.info("[DataExecutors][vector_search] enter.")
            payload["provider"] = 'ollama'
            payload["api_key"] = ''

            search_res = []
            document_id = payload["document_ids"]
            
            if isinstance(document_id, str):
                document_id = [document_id]

            if isinstance(document_id, list):
                payload["document_id"] = document_id  # list[str]
                res = await self.milvus.similarity_search(payload)
                if not res.get("success"): 
                    return res
                search_res = res.get("messages")
            else:
                raise RuntimeError(f"Unexpected document_ids type: {type(document_id)}")
            
            return {
                "success": True,
                "messages": search_res,
            }

        except Exception as e:
            logger.exception(
                f"[DataExecutors][vector_search] error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
