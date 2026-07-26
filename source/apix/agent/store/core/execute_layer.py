import inspect
import json
from typing import Callable, Dict
from uuid import uuid4
from datetime import datetime

from apix.agent.store.utils.message_node_helper import MessageNodeHelper
from apix.agent.store.core.server.data_store.data_server_base import DataServerBase
from apix.agent.store.core.server.cache_store.cache_server_base import CacheServerBase
from apix.agent.store.core.server.file_store.file_server import FileService
from apix.agent.store.core.server.rag_store.rag_server import RagService
from apix.agent.store.utils.decorator import task_handler
from apix.common.utils.logger import logger


class DataExecutors:
    """
    Execution layer.

    Responsibilities:
    - Translate high-level business actions into ordered service calls
    - Coordinate RedisService and MysqlService handlers
    - Normalize return format
    """

    def __init__(
        self, 
        *, 
        cache_store: CacheServerBase, 
        data_store: DataServerBase, 
        file_server: FileService,
        rag_server: RagService
    ):
        self.cache_store = cache_store
        self.data_store = data_store
        self.file_server = file_server
        self.rag_server = rag_server

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
                    f"Task handler '{task_name}' must be async function"
                )

            handlers[task_name] = attr

        return handlers
        
    @task_handler("create_a_user")
    async def create_a_user(self, payload: dict) -> dict:
        """
        Ensure user exists in persistent storage.

        Workflow:
        - Insert user if not exists
        - Update user info if exists

        Redis is NOT involved.
        """
        try:
            logger.trace()
            res = await self.data_store.ensure_user_exists(payload, exist=False)
            if not res.get("success"):
                return res
            
            return await self.data_store.create_a_user(payload)

        except Exception as e:
            logger.exception(
                f"Error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    @task_handler("verify_user")
    async def verify_user(self, payload: dict) -> dict:
        """
        Ensure user exists in persistent storage.

        Workflow:
        - Insert user if not exists
        - Update user info if exists

        Redis is NOT involved.
        """
        try:
            logger.trace()
            return await self.data_store.verify_user(payload)

        except Exception as e:
            logger.exception(
                f"Error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    @task_handler("ensure_user_exists")
    async def ensure_user_exists(self, payload: dict) -> dict:
        """
        Ensure user exists in persistent storage.

        Redis is NOT involved.
        """
        try:
            logger.trace()
            return await self.data_store.ensure_user_exists(payload)

        except Exception as e:
            logger.exception(
                f"Error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    # --------------------------------------------------
    # Conversations
    # --------------------------------------------------

    @task_handler("create_new_conversation")
    async def create_new_conversation(self, payload: dict) -> dict:
        """
        Create a new conversation record.

        Workflow:
        1. Ensure user exists in MySQL
        2. Create a new conversation in MySQL

        Redis is NOT involved.
        """
        try:
            logger.trace()
            # 1. Ensure user exists (idempotent)
            res = await self.data_store.ensure_user_exists(payload)
            if not res.get("success"):
                return res

            # 2. Create conversation
            return await self.data_store.create_conversation(payload)

        except Exception as e:
            logger.exception(
                f"Error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("update_conversation")
    async def update_conversation(self, payload: dict) -> dict:
        """
        Update a conversation record.
        This method could delete a conversation record in mysql.

        Workflow:
        1. Set target conversation messages cache expired in redis if is_deleted is True.
        2. Update conversation recoard in mysql.

        Redis failure NOT fail the whole operation.
        """
        try:
            logger.trace()
            # 1. Update redis
            if payload.get("is_deleted", False):
                expire_payload = payload.copy()
                expire_payload.pop("task_hash", "")
                await self.cache_store.expire_immediately(expire_payload)
            # 2. Update conversation
            return await self.data_store.update_conversation(payload)

        except Exception as e:
            logger.exception(
                f"Error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    @task_handler("fetch_conversation_list")
    async def fetch_conversation_list(self, payload: dict) -> dict:
        """
        Fetch user's conversation list.

        Redis is NOT involved.
        """
        try:
            logger.trace()
            return await self.data_store.fetch_conversation_list(payload)

        except Exception as e:
            logger.exception(
                f"Error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    @task_handler("get_conversation_meta_by_id")
    async def get_conversation_meta_by_id(self, payload: dict) -> dict:
        """
        Fetch user's conversation list.

        Redis is NOT involved.
        """
        try:
            logger.trace()
            return await self.data_store.get_conversation_meta_by_id(payload)

        except Exception as e:
            logger.exception(
                f"Error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    # --------------------------------------------------
    # Conversation Messages
    # --------------------------------------------------

    @task_handler("append_message")
    async def append_message(self, payload: dict) -> dict:
        """
        Append a single message to MySQL and try to backfill Redis.

        Workflow:
        1. Persist message to MySQL (source of truth)
        2. Best-effort append to Redis if cache exists

        Redis failure NOT fail the whole operation.
        """
        try:
            logger.trace()
            messages = payload["messages"]
            # 1. Persist to MySQL
            res = await self.data_store.append_message(payload)
            if not res.get("success"):
                return res

            # 2. Best-effort backfill Redis
            messages_redis = payload.get("messages")
            messages_redis.update(res.get("messages"))
            messages_redis["is_deleted"] = False
            payload.update({
                "messages": messages_redis
            })
            try:
                logger.info(
                    f"Redis backfill payload: {payload}"
                )
                await self.cache_store.append_messages(payload)
            except Exception as e:
                # Redis failure should not break main flow
                logger.warning(
                    f"Redis backfill failed: {e}"
                )

            user_uid = payload["user_uid"]
            conversation_uid = payload["conversation_uid"]
            node_id = messages.get("node_id", "")
            parent_id = messages.get("parent_id", "")
            await self.cache_store.update_current_messages_branch_chain_cache({
                "user_uid": user_uid,
                "conversation_uid": conversation_uid,
                "node_id": node_id,
                "parent_id": parent_id,
            })

            return {
                "success": True,
                "messages": "success",
            }

        except Exception as e:
            logger.exception(
                f"Error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("delete_messages")
    async def delete_messages(self, payload: dict) -> dict:
        """
        Delete one or more message from MySQL and try to expire Redis.

        Workflow:
        - Delete message from MySQL (source of truth)
        - Expire cache in Redis if exists

        Redis failure NOT fail the whole operation.
        """
        try:
            logger.trace()

            try:
                await self.cache_store.expire_immediately(payload)
            except Exception as e:
                # Redis failure should not break main flow
                logger.warning(
                    f"Redis backfill failed: {e}"
                )

            res = await self.data_store.delete_messages(payload)
            if not res.get("success"):
                return res
            
            msg_info = res.get("messages", []) or []
            mem_ids = []
            for info in msg_info:
                mem_id = info.get("id")
                if not mem_id: continue
                mem_ids.append(mem_id)

            if mem_ids:
                sm_payload = {
                    "user_uid": payload.get("user_uid", ""),
                    "conversation_uid": payload.get("conversation_uid", ""),
                    "memory_ids": mem_ids
                }

                res = await self.data_store.delete_shortterm_memory(sm_payload)
                if not res.get("success"):
                    return res

            return {
                "success": True,
                "messages": "success",
            }

        except Exception as e:
            logger.exception(
                f"Error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    def _build_visible_messages(
        self,
        messages,
        current_node_id,
        allow_roles,
        guess_children: bool = True,
    ):

        if not messages:
            return [], {}

        helper = MessageNodeHelper(messages)

        # fallback current node
        if current_node_id is None or current_node_id not in helper.node_map:
            last_node = max(helper.nodes, key=lambda x: x["last_cursor"])
            current_node_id = last_node["node_id"]

        # If current node is not visible (deleted), find the nearest parent node.
        current_node = helper.find_nearest_visible(current_node_id)
        if current_node:
            current_node_id = current_node["node_id"]

        # build branch
        if guess_children:
            branch = helper.build_branch(current_node_id)
        else:
            branch = helper.get_path(current_node_id)

        rows = helper.flatten_branch(branch)

        # strict cutoff
        if not guess_children:
            node = helper.node_map.get(current_node_id)
            if node:
                cutoff = node["last_cursor"]
                rows = [r for r in rows if r["msg_cursor"] <= cutoff]

        # filter deleted for front
        rows = [r for r in rows if not r["is_deleted"]]

        parsed = []
        node_id_chain = []
        for msg in rows:
            if msg.get("role") not in allow_roles:
                continue

            extra = msg.get("extra", {})
            info = msg.get("info", {})

            try:
                if not isinstance(extra, dict) and extra:
                    extra = json.loads(extra)
            except Exception:
                extra = {}

            try:
                if not isinstance(info, dict) and info:
                    info = json.loads(info)
            except Exception:
                info = {}

            msg["extra"] = extra
            msg["info"] = info

            parsed.append(msg)
            if len(node_id_chain) == 0 or node_id_chain[-1] != msg.get("node_id"):
                node_id_chain.append(msg.get("node_id"))

        logger.info("Current node_id_chain: ", node_id_chain)
        # build branches info
        branches = {}

        if guess_children:
            visited_parent = set()

            for node in branch:
                parent_id = node["parent_id"]

                if parent_id in visited_parent:
                    continue

                visited_parent.add(parent_id)

                siblings = helper.get_children(parent_id)

                visible_siblings = [c for c in siblings if c.get("visible")]

                if len(visible_siblings) > 1:
                    branches[parent_id] = [
                        {
                            "node_id": c["node_id"],
                            "cursor": c["first_cursor"],
                        }
                        for c in visible_siblings
                    ]

        return parsed, branches, node_id_chain

    @task_handler("get_messages")
    async def get_messages(self, payload: dict) -> dict:
        try:
            logger.trace()

            current_node_id = payload.get("current_node_id")

            try:
                if current_node_id == '-':
                    cache_chain_res = await self.cache_store.get_current_messages_branch_chain({
                        "user_uid": payload["user_uid"],
                        "conversation_uid": payload["conversation_uid"],
                    })
                    if cache_chain_res.get("success") and cache_chain_res.get("cache_hit"):
                        cached_chain = cache_chain_res.get("messages")
                        if isinstance(cached_chain, list) and len(cached_chain)>0:
                            current_node_id = cached_chain[-1]
            except Exception as e:
                logger.warning(
                    f"Get cached message id chain fialed: {e}, skip."
                )

            # 1. Redis
            redis_res = await self.cache_store.get_recent_messages(payload)
            if redis_res.get("success") and redis_res.get("cache_hit"):
                messages = redis_res.get("messages", [])

                parsed_messages, branches, node_id_chain = self._build_visible_messages(
                    messages,
                    current_node_id,
                    allow_roles=('user', 'ai', 'system', 'tool', 'info'),
                    guess_children=False
                )

                payload["node_id_chain"] = node_id_chain
                await self.cache_store.cache_current_messages_branch_chain(payload)

                redis_res["messages"] = parsed_messages
                redis_res["branches"] = branches
                return redis_res

            # 2. MySQL
            mysql_payload = payload.copy()
            mysql_payload["cursor"] = 1

            mysql_res = await self.data_store.fetch_messages_after_cursor(mysql_payload)
            if not mysql_res.get("success"):
                return mysql_res

            messages = mysql_res.get("messages", [])
            if not messages:
                return mysql_res

            # 3. backfill
            try:
                backfill_payload = payload.copy()
                backfill_payload["messages"] = messages
                await self.cache_store.backfill_messages(backfill_payload)
            except Exception as e:
                logger.warning(
                    f"Redis backfill failed: {e}"
                )

            # 4. build branch
            parsed_messages, branches, node_id_chain = self._build_visible_messages(
                messages,
                current_node_id,
                allow_roles=('user', 'ai', 'system', 'tool', 'info'),
                guess_children=False
            )

            # 5. cache current node chain
            payload["node_id_chain"] = node_id_chain
            await self.cache_store.cache_current_messages_branch_chain(payload)

            mysql_res["messages"] = parsed_messages
            mysql_res["branches"] = branches
            return mysql_res

        except Exception as e:
            logger.exception(
                f"Error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("get_messages_for_user")
    async def get_messages_for_user(self, payload: dict) -> dict:
        try:
            logger.trace()

            current_node_id = payload.get("current_node_id")

            try:
                if current_node_id == '-':
                    cache_chain_res = await self.cache_store.get_current_messages_branch_chain({
                        "user_uid": payload["user_uid"],
                        "conversation_uid": payload["conversation_uid"],
                    })
                    if cache_chain_res.get("success") and cache_chain_res.get("cache_hit"):
                        cached_chain = cache_chain_res.get("messages")
                        if isinstance(cached_chain, list) and len(cached_chain)>0:
                            current_node_id = cached_chain[-1]
            except Exception as e:
                logger.warning(
                    f"Get cached message id chain fialed: {e}, skip."
                )

            # 1. Redis
            redis_res = await self.cache_store.get_recent_messages(payload)
            if redis_res.get("success") and redis_res.get("cache_hit"):
                messages = redis_res.get("messages", [])

                parsed_messages, branches, node_id_chain = self._build_visible_messages(
                    messages,
                    current_node_id,
                    allow_roles=('user', 'ai', 'info')
                )

                payload["node_id_chain"] = node_id_chain
                await self.cache_store.cache_current_messages_branch_chain(payload)

                redis_res["messages"] = parsed_messages
                redis_res["branches"] = branches
                return redis_res

            # 2. MySQL
            mysql_payload = payload.copy()
            mysql_payload["cursor"] = 1

            mysql_res = await self.data_store.fetch_messages_after_cursor(mysql_payload)
            if not mysql_res.get("success"):
                return mysql_res

            messages = mysql_res.get("messages", [])
            if not messages:
                return mysql_res

            # 3. backfill
            try:
                backfill_payload = payload.copy()
                backfill_payload["messages"] = messages
                await self.cache_store.backfill_messages(backfill_payload)
            except Exception as e:
                logger.warning(
                    f"Redis backfill failed: {e}"
                )

            # 4. build branch
            parsed_messages, branches, node_id_chain = self._build_visible_messages(
                messages,
                current_node_id,
                allow_roles=('user', 'ai', 'info')
            )

            # 5. cache current node chain
            payload["node_id_chain"] = node_id_chain
            await self.cache_store.cache_current_messages_branch_chain(payload)

            mysql_res["messages"] = parsed_messages
            mysql_res["branches"] = branches
            return mysql_res

        except Exception as e:
            logger.exception(
                f"Error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    @task_handler("search_messages_by_keyword")
    async def search_messages_by_keyword(self, payload: dict) -> dict:
        try:
            logger.trace()
            return await self.data_store.search_messages_by_keyword(payload)

        except Exception as e:
            logger.exception(
                f"Error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    @task_handler("get_current_messages_branch_chain")
    async def get_current_messages_branch_chain(self, payload: dict) -> dict:
        try:
            logger.trace()
            return await self.cache_store.get_current_messages_branch_chain(payload)

        except Exception as e:
            logger.exception(
                f"Error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    # --------------------------------------------------
    # Files
    # --------------------------------------------------

    @task_handler("upload_file_to_workspace")
    async def upload_file_to_workspace(self, payload: dict) -> dict:
        """
        Move selected files into workspace.
        """
        try:
            logger.trace()
            res = await self.data_store.ensure_user_exists(payload)
            if not res.get("success"):
                return res
            return await self.file_server.save_file(payload)

        except Exception as e:
            logger.exception(
                f"Error: {e}"
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
            logger.trace()

            res = await self.data_store.ensure_user_exists(payload)
            if not res.get("success"):
                return res

            file_res = await self.file_server.handle_skill_package(payload)
            if not file_res.get("success"):
                return file_res
            
            skill_payload = {
                "user_uid": payload["user_uid"],
                "skills": file_res.get("messages", []),
            }
            mysql_res = await self.data_store.insert_skill_info(skill_payload)
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
                f"Error: {e}"
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
            logger.trace()
            return await self.data_store.update_skill_status(payload)

        except Exception as e:
            logger.exception(
                f"Error: {e}"
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
            logger.trace()
            return await self.data_store.fetch_available_skills(payload)

        except Exception as e:
            logger.exception(
                f"Error: {e}"
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
            logger.trace()
            return await self.data_store.fetch_target_skill(payload)

        except Exception as e:
            logger.exception(
                f"Error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    # --------------------------------------------------
    # Short-term Memory
    # --------------------------------------------------
    
    @task_handler("fetch_shortterm_memory")
    async def fetch_shortterm_memory(self, payload: dict) -> dict:
        """
        Fetch shortterm memory.
        """
        try:
            logger.trace()

            mysql_res = await self.data_store.fetch_shortterm_memory(payload)

            return mysql_res

        except Exception as e:
            logger.exception(
                f"Error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    @task_handler("insert_shortterm_memory")
    async def insert_shortterm_memory(self, payload: dict) -> dict:
        """
        Insert shortterm memory.
        """
        try:
            logger.trace()

            mysql_res = await self.data_store.insert_shortterm_memory(payload)

            return mysql_res

        except Exception as e:
            logger.exception(
                f"Error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    # --------------------------------------------------
    # LLM Provider
    # --------------------------------------------------

    @task_handler("create_llm_provider")
    async def create_llm_provider(self, payload: dict) -> dict:
        """
        Insert a llm provider meta in database.
        """
        try:
            logger.trace()
            provider_id = str(uuid4().hex)
            payload["provider_id"] = provider_id

            return await self.data_store.create_llm_provider(payload)
        
        except Exception as e:
            logger.exception(
                f"Error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    @task_handler("get_llm_providers")
    async def get_llm_providers(self, payload: dict) -> dict:
        """
        Get all llm provider meta in database.
        """
        try:
            logger.trace()

            mysql_res = await self.data_store.get_llm_providers(payload)
            if not mysql_res.get("success"):
                return mysql_res
            
            parsed = []
            providers = mysql_res.get("messages", []) or []
            for p in providers:
                model_list = p.get("model_list", []) or []
                if not isinstance(model_list, list):
                    p["model_list"] = json.loads(model_list)
                parsed.append(p)
            
            mysql_res["messages"] = parsed
            return mysql_res
        
        except Exception as e:
            logger.exception(
                f"Error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    @task_handler("get_llm_provider_by_id")
    async def get_llm_provider_by_id(self, payload: dict) -> dict:
        """
        Get a llm provider meta in database.
        """
        try:
            logger.trace()

            mysql_res = await self.data_store.get_llm_provider_by_id(payload)
            if not mysql_res.get("success"):
                return mysql_res
            
            parsed = []
            providers = mysql_res.get("messages", []) or []
            for p in providers:
                model_list = p.get("model_list", []) or []
                if not isinstance(model_list, list):
                    p["model_list"] = json.loads(model_list)
                parsed.append(p)
            
            mysql_res["messages"] = parsed
            return mysql_res
        
        except Exception as e:
            logger.exception(
                f"Error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    @task_handler("update_llm_provider")
    async def update_llm_provider(self, payload: dict) -> dict:
        """
        Update a llm provider meta in database, include is_deleted status.
        """
        try:
            logger.trace()

            return await self.data_store.update_llm_provider(payload)
        
        except Exception as e:
            logger.exception(
                f"Error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    # --------------------------------------------------
    # MCP Server
    # --------------------------------------------------

    @task_handler("create_mcp_server")
    async def create_mcp_server(self, payload: dict) -> dict:
        """
        Insert a mcp server meta in database.
        """
        try:
            logger.trace()

            mcp_id = str(uuid4().hex)
            payload["mcp_id"] = mcp_id

            return await self.data_store.create_mcp_server(payload)

        except Exception as e:
            logger.exception(
                f"Error: {e}"
            )

            return {
                "success": False,
                "messages": f"fail: {e}",
            }


    @task_handler("get_mcp_servers")
    async def get_mcp_servers(self, payload: dict) -> dict:
        """
        Get all mcp server meta in database.
        """
        try:
            logger.trace()

            mysql_res = await self.data_store.get_mcp_servers(payload)

            if not mysql_res.get("success"):
                return mysql_res

            parsed = []

            servers = mysql_res.get("messages", []) or []

            for server in servers:

                config = server.get("config")

                if config and not isinstance(config, (dict, list)):
                    try:
                        server["config"] = json.loads(config)
                    except Exception:
                        server["config"] = {}

                parsed.append(server)

            mysql_res["messages"] = parsed

            return mysql_res

        except Exception as e:
            logger.exception(
                f"Error: {e}"
            )

            return {
                "success": False,
                "messages": f"fail: {e}",
            }


    @task_handler("get_enabled_mcp_servers")
    async def get_enabled_mcp_servers(self, payload: dict) -> dict:
        """
        Get enabled mcp server meta in database.
        """
        try:
            logger.trace()

            mysql_res = await self.data_store.get_enabled_mcp_servers(payload)

            if not mysql_res.get("success"):
                return mysql_res

            parsed = []

            servers = mysql_res.get("messages", []) or []

            for server in servers:

                config = server.get("config")

                if config and not isinstance(config, (dict, list)):
                    try:
                        server["config"] = json.loads(config)
                    except Exception:
                        server["config"] = {}

                parsed.append(server)

            mysql_res["messages"] = parsed

            return mysql_res

        except Exception as e:
            logger.exception(
                f"Error: {e}"
            )

            return {
                "success": False,
                "messages": f"fail: {e}",
            }


    @task_handler("update_mcp_server")
    async def update_mcp_server(self, payload: dict) -> dict:
        """
        Update a mcp server meta in database,
        include enabled/tool_count/is_deleted status.
        """
        try:
            logger.trace()

            return await self.data_store.update_mcp_server(payload)

        except Exception as e:
            logger.exception(
                f"Error: {e}"
            )

            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        

    @task_handler("create_cron_task")
    async def create_cron_task(self, payload: dict) -> dict:
        """
        Insert a cron task meta in database.
        """
        try:
            logger.trace()

            task_id = str(uuid4().hex)
            payload["task_id"] = task_id

            return await self.data_store.create_cron_task(payload)

        except Exception as e:
            logger.exception(
                f"Error: {e}"
            )

            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        

    @task_handler("get_all_enabled_cron_tasks")
    async def get_all_enabled_cron_tasks(self, payload: dict) -> dict:
        """
        Get all cron task meta in database.
        """
        try:
            logger.trace()

            mysql_res = await self.data_store.get_all_enabled_cron_tasks(payload)

            if not mysql_res.get("success"):
                return mysql_res

            parsed = []

            crons = mysql_res.get("messages", []) or []

            for cron in crons:

                config = cron.get("extra_config")

                if config and not isinstance(config, (dict, list)):
                    try:
                        cron["extra_config"] = json.loads(config)
                    except Exception:
                        cron["extra_config"] = {}

                parsed.append(cron)

            mysql_res["messages"] = parsed

            return mysql_res

        except Exception as e:
            logger.exception(
                f"Error: {e}"
            )

            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        

    @task_handler("get_cron_tasks")
    async def get_cron_tasks(self, payload: dict) -> dict:
        """
        Get all cron task meta in database.
        """
        try:
            logger.trace()

            mysql_res = await self.data_store.get_cron_tasks(payload)

            if not mysql_res.get("success"):
                return mysql_res

            parsed = []

            crons = mysql_res.get("messages", []) or []

            for cron in crons:

                config = cron.get("extra_config")

                if config and not isinstance(config, (dict, list)):
                    try:
                        cron["extra_config"] = json.loads(config)
                    except Exception:
                        cron["extra_config"] = {}

                parsed.append(cron)

            mysql_res["messages"] = parsed

            return mysql_res

        except Exception as e:
            logger.exception(
                f"Error: {e}"
            )

            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        

    @task_handler("get_cron_task_by_id")
    async def get_cron_task_by_id(self, payload: dict) -> dict:
        """
        Get a cron task meta in database.
        """
        try:
            logger.trace()

            mysql_res = await self.data_store.get_cron_task_by_id(payload)

            if not mysql_res.get("success"):
                return mysql_res

            parsed = []

            crons = mysql_res.get("messages", []) or []

            for cron in crons:

                config = cron.get("extra_config")

                if config and not isinstance(config, (dict, list)):
                    try:
                        cron["extra_config"] = json.loads(config)
                    except Exception:
                        cron["extra_config"] = {}

                parsed.append(cron)

            mysql_res["messages"] = parsed

            return mysql_res

        except Exception as e:
            logger.exception(
                f"Error: {e}"
            )

            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        

    @task_handler("update_cron_task")
    async def update_cron_task(self, payload: dict) -> dict:
        """
        Update a cron task meta in database,
        include enabled/is_deleted status.
        """
        try:
            logger.trace()

            return await self.data_store.update_cron_task(payload)

        except Exception as e:
            logger.exception(
                f"Error: {e}"
            )

            return {
                "success": False,
                "messages": f"fail: {e}",
            }
