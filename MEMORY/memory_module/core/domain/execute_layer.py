import inspect
import json
from typing import Callable, Dict
from uuid import uuid4
from core.commons.logger import logger

from core.domain.redis_server import RedisService
from core.domain.mysql_server import MysqlService
from core.domain.helper.message_node_helper import AgentNodeHelper
from core.commons.decorator import task_handler


class DataExecutors:
    """
    Execution layer.

    Responsibilities:
    - Translate high-level business actions into ordered service calls
    - Coordinate RedisService and MysqlService handlers
    - Normalize return format
    """

    def __init__(self, *, redis_store: RedisService, mysql_store: MysqlService):
        self.redis = redis_store
        self.mysql = mysql_store
                


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
            logger.info("[DataExecutors][create_a_user] enter.")
            res = await self.mysql.ensure_user_exists(payload, exist=False)
            if not res.get("success"):
                return res
            
            return await self.mysql.create_a_user(payload)

        except Exception as e:
            logger.exception(
                f"[DataExecutors][create_a_user] error: {e}"
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
            logger.info("[DataExecutors][verify_user] enter.")
            return await self.mysql.verify_user(payload)

        except Exception as e:
            logger.exception(
                f"[DataExecutors][verify_user] error: {e}"
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
            logger.info("[DataExecutors][create_new_conversation] enter.")
            # 1. Ensure user exists (idempotent)
            res = await self.mysql.ensure_user_exists(payload)
            if not res.get("success"):
                return res

            # 2. Create conversation
            return await self.mysql.create_conversation(payload)

        except Exception as e:
            logger.exception(
                f"[DataExecutors][create_new_conversation] error: {e}"
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
            logger.info("[DataExecutors][update_conversation] enter.")
            # 1. Update redis
            if payload.get("is_deleted", False):
                expire_payload = payload.copy()
                expire_payload.pop("task_hash", "")
                await self.redis.expire_immediately(expire_payload)
            # 2. Update conversation
            return await self.mysql.update_conversation(payload)

        except Exception as e:
            logger.exception(
                f"[DataExecutors][update_conversation] error: {e}"
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
            logger.info("[DataExecutors][fetch_conversation_list] enter.")
            return await self.mysql.fetch_conversation_list(payload)

        except Exception as e:
            logger.exception(
                f"[DataExecutors][fetch_conversation_list] error: {e}"
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
            logger.info("[DataExecutors][append_message] enter.")
            messages = payload["messages"]
            # 1. Persist to MySQL
            res = await self.mysql.append_message(payload)
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
                    f"[DataExecutors][append_message] Redis backfill payload: {payload}"
                )
                await self.redis.append_messages(payload)
            except Exception as e:
                # Redis failure should not break main flow
                logger.warning(
                    f"[DataExecutors][append_message] Redis backfill failed: {e}"
                )

            user_uid = payload["client_id"]
            conversation_id = payload["history_id"]
            node_id = messages.get("node_id", "")
            parent_id = messages.get("parent_id", "")
            await self.redis.update_current_messages_branch_chain_cache({
                "client_id": user_uid,
                "history_id": conversation_id,
                "node_id": node_id,
                "parent_id": parent_id,
            })

            return {
                "success": True,
                "messages": "success",
            }

        except Exception as e:
            logger.exception(
                f"[DataExecutors][append_message] error: {e}"
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
            logger.info("[DataExecutors][delete_messages] enter.")

            try:
                await self.redis.expire_immediately(payload)
            except Exception as e:
                # Redis failure should not break main flow
                logger.warning(
                    f"[DataExecutors][delete_messages] Redis backfill failed: {e}"
                )

            res = await self.mysql.delete_messages(payload)
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
                    "client_id": payload.get("client_id", ""),
                    "history_id": payload.get("history_id", ""),
                    "memory_id": mem_ids
                }

                res = await self.mysql.delete_shortterm_memory(sm_payload)
                if not res.get("success"):
                    return res

            return {
                "success": True,
                "messages": "success",
            }

        except Exception as e:
            logger.exception(
                f"[DataExecutors][delete_messages] error: {e}"
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

        helper = AgentNodeHelper(messages)

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

        logger.info("[_build_visible_messages] node_id_chain: ", node_id_chain)
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
            logger.info("[DataExecutors][get_messages] enter.")

            current_node_id = payload.get("current_node_id")

            try:
                if current_node_id == '-':
                    cache_chain_res = await self.redis.get_current_messages_branch_chain({
                        "client_id": payload["client_id"],
                        "history_id": payload["history_id"],
                    })
                    if cache_chain_res.get("success") and cache_chain_res.get("cache_hit"):
                        cached_chain = cache_chain_res.get("messages")
                        if isinstance(cached_chain, list) and len(cached_chain)>0:
                            current_node_id = cached_chain[-1]
            except Exception as e:
                logger.warning(
                    f"[DataExecutors][get_messages] warning: get cached message id chain fialed: {e}, skip."
                )

            # 1. Redis
            redis_res = await self.redis.get_recent_messages(payload)
            if redis_res.get("success") and redis_res.get("cache_hit"):
                messages = redis_res.get("messages", [])

                parsed_messages, branches, node_id_chain = self._build_visible_messages(
                    messages,
                    current_node_id,
                    allow_roles=('human', 'ai', 'system', 'tools'),
                    guess_children=False
                )

                payload["node_id_chain"] = node_id_chain
                await self.redis.cache_current_messages_branch_chain(payload)

                redis_res["messages"] = parsed_messages
                redis_res["branches"] = branches
                return redis_res

            # 2. MySQL
            mysql_payload = payload.copy()
            mysql_payload["cursor"] = 1

            mysql_res = await self.mysql.fetch_messages_after_cursor(mysql_payload)
            if not mysql_res.get("success"):
                return mysql_res

            messages = mysql_res.get("messages", [])
            if not messages:
                return mysql_res

            # 3. backfill
            try:
                backfill_payload = payload.copy()
                backfill_payload["messages"] = messages
                await self.redis.backfill_messages(backfill_payload)
            except Exception as e:
                logger.warning(
                    f"[DataExecutors][get_messages] Redis backfill failed: {e}"
                )

            # 4. build branch
            parsed_messages, branches, node_id_chain = self._build_visible_messages(
                messages,
                current_node_id,
                allow_roles=('human', 'ai', 'system', 'tools'),
                guess_children=False
            )

            # 5. cache current node chain
            payload["node_id_chain"] = node_id_chain
            await self.redis.cache_current_messages_branch_chain(payload)

            mysql_res["messages"] = parsed_messages
            mysql_res["branches"] = branches
            return mysql_res

        except Exception as e:
            logger.exception(
                f"[DataExecutors][get_messages] error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("get_messages_for_user")
    async def get_messages_for_user(self, payload: dict) -> dict:
        try:
            logger.info("[DataExecutors][get_messages_for_user] enter.")

            current_node_id = payload.get("current_node_id")

            try:
                if current_node_id == '-':
                    cache_chain_res = await self.redis.get_current_messages_branch_chain({
                        "client_id": payload["client_id"],
                        "history_id": payload["history_id"],
                    })
                    if cache_chain_res.get("success") and cache_chain_res.get("cache_hit"):
                        cached_chain = cache_chain_res.get("messages")
                        if isinstance(cached_chain, list) and len(cached_chain)>0:
                            current_node_id = cached_chain[-1]
            except Exception as e:
                logger.warning(
                    f"[DataExecutors][get_messages] warning: get cached message id chain fialed: {e}, skip."
                )

            # 1. Redis
            redis_res = await self.redis.get_recent_messages(payload)
            if redis_res.get("success") and redis_res.get("cache_hit"):
                messages = redis_res.get("messages", [])

                parsed_messages, branches, node_id_chain = self._build_visible_messages(
                    messages,
                    current_node_id,
                    allow_roles=('human', 'ai', 'info')
                )

                payload["node_id_chain"] = node_id_chain
                await self.redis.cache_current_messages_branch_chain(payload)

                redis_res["messages"] = parsed_messages
                redis_res["branches"] = branches
                return redis_res

            # 2. MySQL
            mysql_payload = payload.copy()
            mysql_payload["cursor"] = 1

            mysql_res = await self.mysql.fetch_messages_after_cursor(mysql_payload)
            if not mysql_res.get("success"):
                return mysql_res

            messages = mysql_res.get("messages", [])
            if not messages:
                return mysql_res

            # 3. backfill
            try:
                backfill_payload = payload.copy()
                backfill_payload["messages"] = messages
                await self.redis.backfill_messages(backfill_payload)
            except Exception as e:
                logger.warning(
                    f"[DataExecutors][get_messages_for_user] Redis backfill failed: {e}"
                )

            # 4. build branch
            parsed_messages, branches, node_id_chain = self._build_visible_messages(
                messages,
                current_node_id,
                allow_roles=('human', 'ai', 'info')
            )

            # 5. cache current node chain
            payload["node_id_chain"] = node_id_chain
            await self.redis.cache_current_messages_branch_chain(payload)

            mysql_res["messages"] = parsed_messages
            mysql_res["branches"] = branches
            return mysql_res

        except Exception as e:
            logger.exception(
                f"[DataExecutors][get_messages_for_user] error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    @task_handler("search_messages_by_keyword")
    async def search_messages_by_keyword(self, payload: dict) -> dict:
        try:
            logger.info("[DataExecutors][search_messages_by_keyword] enter.")
            return await self.mysql.search_messages_by_keyword(payload)

        except Exception as e:
            logger.exception(
                f"[DataExecutors][search_messages_by_keyword] error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    @task_handler("get_current_messages_branch_chain")
    async def get_current_messages_branch_chain(self, payload: dict) -> dict:
        try:
            logger.info("[DataExecutors][get_current_messages_branch_chain] enter.")
            return await self.redis.get_current_messages_branch_chain(payload)

        except Exception as e:
            logger.exception(
                f"[DataExecutors][get_current_messages_branch_chain] error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    # --------------------------------------------------
    # Files
    # --------------------------------------------------

    @task_handler("insert_file_info")
    async def insert_file_info(self, payload: dict) -> dict:
        """
        Insert new files info.

        No redis invoke.
        """
        try:
            logger.info("[DataExecutors][insert_file_info] enter.")
            res = await self.mysql.ensure_user_exists(payload)
            if not res.get("success"):
                return res
            return await self.mysql.insert_file_info(payload)

        except Exception as e:
            logger.exception(
                f"[DataExecutors][insert_file_info] error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("update_file_info")
    async def update_file_info(self, payload: dict) -> dict:
        """
        Fetch recent files info.
        This method could used to delete a file record in mysql.

        No redis invoke.
        """
        try:
            logger.info("[DataExecutors][update_file_info] enter.")
            return await self.mysql.update_file_info(payload)

        except Exception as e:
            logger.exception(
                f"[DataExecutors][update_file_info] error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("get_recent_files")
    async def get_recent_files(self, payload: dict) -> dict:
        """
        Fetch recent files info.

        No redis invoke.
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

    # --------------------------------------------------
    # Short-term Memory
    # --------------------------------------------------
    
    @task_handler("fetch_shortterm_memory")
    async def fetch_shortterm_memory(self, payload: dict) -> dict:
        """
        Fetch shortterm memory.
        """
        try:
            logger.info("[DataExecutors][fetch_shortterm_memory] enter.")

            mysql_res = await self.mysql.fetch_shortterm_memory(payload)

            return mysql_res

        except Exception as e:
            logger.exception(
                f"[DataExecutors][fetch_shortterm_memory] error: {e}"
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
            logger.info("[DataExecutors][insert_shortterm_memory] enter.")

            mysql_res = await self.mysql.insert_shortterm_memory(payload)

            return mysql_res

        except Exception as e:
            logger.exception(
                f"[DataExecutors][insert_shortterm_memory] error: {e}"
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
            logger.info("[DataExecutors][create_llm_provider] enter.")
            provider_id = str(uuid4().hex)
            payload["provider_id"] = provider_id

            return await self.mysql.create_llm_provider(payload)
        
        except Exception as e:
            logger.exception(
                f"[DataExecutors][create_llm_provider] error: {e}"
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
            logger.info("[DataExecutors][get_llm_providers] enter.")

            mysql_res = await self.mysql.get_llm_providers(payload)
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
                f"[DataExecutors][get_llm_providers] error: {e}"
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
            logger.info("[DataExecutors][get_llm_provider_by_id] enter.")

            mysql_res = await self.mysql.get_llm_provider_by_id(payload)
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
                f"[DataExecutors][get_llm_provider_by_id] error: {e}"
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
            logger.info("[DataExecutors][update_llm_provider] enter.")

            return await self.mysql.update_llm_provider(payload)
        
        except Exception as e:
            logger.exception(
                f"[DataExecutors][update_llm_provider] error: {e}"
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
            logger.info("[DataExecutors][create_mcp_server] enter.")

            mcp_id = str(uuid4().hex)
            payload["mcp_id"] = mcp_id

            return await self.mysql.create_mcp_server(payload)

        except Exception as e:
            logger.exception(
                f"[DataExecutors][create_mcp_server] error: {e}"
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
            logger.info("[DataExecutors][get_mcp_servers] enter.")

            mysql_res = await self.mysql.get_mcp_servers(payload)

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
                f"[DataExecutors][get_mcp_servers] error: {e}"
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
            logger.info("[DataExecutors][get_enabled_mcp_servers] enter.")

            mysql_res = await self.mysql.get_enabled_mcp_servers(payload)

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
                f"[DataExecutors][get_enabled_mcp_servers] error: {e}"
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
            logger.info("[DataExecutors][update_mcp_server] enter.")

            return await self.mysql.update_mcp_server(payload)

        except Exception as e:
            logger.exception(
                f"[DataExecutors][update_mcp_server] error: {e}"
            )

            return {
                "success": False,
                "messages": f"fail: {e}",
            }