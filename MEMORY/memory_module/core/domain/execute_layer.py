import asyncio
import inspect
import json
import time
from typing import Callable, Dict
from core.commons.logger import logger

from core.domain.redis_server import RedisService
from core.domain.mysql_server import MysqlService
from core.domain.helper.message_node_helper import AgentNodeHelper
from core.notification.notice import notice_ai, construct_notice_payload
from core.commons.decorator import task_handler
from public import TASK_RUNNING_STATUS, TASK_FINISHING_STATUS


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
        
    @task_handler("ensure_user_exists")
    async def ensure_user_exists(self, payload: dict) -> dict:
        """
        Ensure user exists in persistent storage.

        Workflow:
        - Insert user if not exists
        - Update user info if exists

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

        # -----------------------------
        # fallback current node
        # -----------------------------
        if current_node_id is None or current_node_id not in helper.node_map:
            last_node = max(helper.nodes, key=lambda x: x["last_cursor"])
            current_node_id = last_node["node_id"]

        # ✅ 如果当前节点不可见，向上找最近可见节点
        current_node = helper.find_nearest_visible(current_node_id)
        if current_node:
            current_node_id = current_node["node_id"]

        # -----------------------------
        # build branch
        # -----------------------------
        if guess_children:
            branch = helper.build_branch(current_node_id)
        else:
            branch = helper.get_path(current_node_id)

        rows = helper.flatten_branch(branch)

        # -----------------------------
        # strict cutoff
        # -----------------------------
        if not guess_children:
            node = helper.node_map.get(current_node_id)
            if node:
                cutoff = node["last_cursor"]
                rows = [r for r in rows if r["msg_cursor"] <= cutoff]

        # -----------------------------
        # ✅ 过滤 deleted（仅展示层）
        # -----------------------------
        rows = [r for r in rows if not r["is_deleted"]]

        # -----------------------------
        # parse json fields
        # -----------------------------
        parsed = []
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

        # -----------------------------
        # branches（分支信息）
        # -----------------------------
        branches = {}

        if guess_children:
            visited_parent = set()

            for node in branch:
                parent_id = node["parent_id"]

                if parent_id in visited_parent:
                    continue

                visited_parent.add(parent_id)

                siblings = helper.get_children(parent_id)

                # ✅ 只展示“有可见内容”的兄弟节点
                visible_siblings = [c for c in siblings if c.get("visible")]

                if len(visible_siblings) > 1:
                    branches[parent_id] = [
                        {
                            "node_id": c["node_id"],
                            "cursor": c["first_cursor"],
                        }
                        for c in visible_siblings
                    ]

        return parsed, branches

    @task_handler("get_messages")
    async def get_messages(self, payload: dict) -> dict:
        try:
            logger.info("[DataExecutors][get_messages] enter.")

            current_node_id = payload.get("current_node_id")

            # 1. Redis
            redis_res = await self.redis.get_recent_messages(payload)
            if redis_res.get("success") and redis_res.get("cache_hit"):
                messages = redis_res.get("messages", [])

                parsed_messages, branches = self._build_visible_messages(
                    messages,
                    current_node_id,
                    allow_roles=('human', 'ai', 'system', 'tools'),
                    guess_children=False
                )

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
            parsed_messages, branches = self._build_visible_messages(
                messages,
                current_node_id,
                allow_roles=('human', 'ai', 'system', 'tools'),
                guess_children=False
            )

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

            # 1. Redis
            redis_res = await self.redis.get_recent_messages(payload)
            if redis_res.get("success") and redis_res.get("cache_hit"):
                messages = redis_res.get("messages", [])

                parsed_messages, branches = self._build_visible_messages(
                    messages,
                    current_node_id,
                    allow_roles=('human', 'ai', 'info')
                )

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
            parsed_messages, branches = self._build_visible_messages(
                messages,
                current_node_id,
                allow_roles=('human', 'ai', 'info')
            )

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
        
    @task_handler("_get_messages_for_user")
    async def _get_messages_for_user(self, payload: dict) -> dict:
        """
        Deprecated.
        Fetch conversation timeline for user rendering.

        Workflow:
        1. Fetch messages from MySQL (already filtered: no system / tools)
        2. Fetch task_info from MySQL
        3. Convert task_info into virtual system messages
        4. Merge messages and virtual system messages
        5. Sort by created_at (TIMESTAMP)
        """

        try:
            logger.info("[DataExecutors][get_messages_for_user] enter.")

            user_uid = payload["client_id"]
            conversation_uid = payload["history_id"]

            # 1. Fetch messages from MySQL
            msg_payload = {
                "client_id": user_uid,
                "history_id": conversation_uid,
            }

            msg_res = await self.mysql.fetch_messages_for_user(msg_payload)
            if not msg_res.get("success"):
                return msg_res

            raw_messages = msg_res.get("messages", [])
            messages = []
            for msg in raw_messages:
                extra = msg.get('extra', {})
                info = msg.get('info', {})
                extra = json.loads(extra) if not isinstance(extra, dict) and extra else {}
                info = json.loads(info) if not isinstance(info, dict) and info else {}
                msg.update({
                    "extra": extra,
                    "info": info,
                })
                messages.append(msg)

            # 2. Fetch task_info from MySQL
            task_payload = {
                "client_id": user_uid,
                "history_id": conversation_uid,
            }

            task_res = await self.mysql.fetch_batches_task_info(task_payload)
            if not task_res.get("success"):
                return task_res

            tasks = task_res.get("messages", [])

            # 3. Convert task_info to virtual system messages
            #    Keep the same format with those messages from mysql
            virtual_system_messages = []
            for task in tasks:
                task_payload = task.get("payload")
                if not isinstance(task_payload, dict) and task_payload:
                    task_payload = json.loads(task_payload)
                    model_config = task_payload.get("config")
                if not isinstance(model_config, dict) and model_config:
                    model_config = json.loads(model_config)
                virtual_system_messages.append({
                    "role": "system",
                    "content": "",
                    "think": "",
                    "extra": {},
                    "info": {
                        "desc": task_payload.get("describe", "Null"),
                        "status": task.get("status", "Unsigned status"),
                        "task_id": task.get("task_id", "Error to get task_id"),
                        "tool_name": task_payload.get("tool_name", "Unsigned tool"),
                    },
                    "msg_cursor": -1,
                    "created_at": task.get("created_at"),
                })

            # --------------------------------------------------
            # 4. Merge & sort timeline
            # --------------------------------------------------
            timeline = messages + virtual_system_messages
            timeline.sort(key=lambda x: x.get("created_at"))

            return {
                "success": True,
                "messages": timeline,
            }

        except Exception as e:
            logger.exception(
                f"[DataExecutors][get_messages_for_user] error: {e}"
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
    # Tool Tasks
    # --------------------------------------------------

    @task_handler("create_task")
    async def create_task(self, payload: dict) -> dict:
        """
        Create a runtime task in Redis and Mysql.
        Redis acts as runtime lock.

        Workflow:
        1. Create task in Redis
        2. Create task in Mysql
        """
        try:
            logger.info("[DataExecutors][create_task] enter.")
            res = await self.mysql.ensure_user_exists(payload)
            if not res.get("success"):
                return res
            result = await self.redis.create_task(payload)
            if result.get("success"):
                await self.mysql.create_task_record(payload)
                notice_payload = construct_notice_payload(
                    task_id=payload.get('task_id'),
                    user_uid=payload.get('client_id'),
                    conversation_uid=payload.get('history_id'),
                    status=payload.get('status'),
                    result={},
                    payload=payload.get('payload'),
                )
                asyncio.create_task(notice_ai(notice_payload, 'Task created.', invoke=False))
            return result
        except Exception as e:
            logger.exception(
                f"[DataExecutors][create_task] error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("update_task")
    async def update_task(self, payload: dict) -> dict:
        """
        Update runtime task state.

        Workflow:
        1. Update task in Redis
        2.  - If finished, update to MySQL, notice and invoke ai
            - If not finish, do not update to MySQL, notice but not invoke ai
        """
        try:
            logger.info("[DataExecutors][update_task] enter.")

            # 1. update task in redis
            redis_res = await self.redis.update_task(payload)
            if not redis_res.get("success"):
                # redis update failed -> mark task failed in mysql
                mysql_payload = {
                    "task_id": payload["task_id"],
                    "status": "failed",
                    "result": [{"failed": redis_res.get("messages")}],
                }

                result = await self.mysql.update_task_result(mysql_payload)
                messages = result.get("messages", {})

                notice_payload = construct_notice_payload(
                    task_id=messages.get("task_id"),
                    user_uid=messages.get("user_uid"),
                    conversation_uid=messages.get("conversation_uid"),
                    status=messages.get("status"),
                    result=messages.get("result"),
                    payload=messages.get("payload"),
                )

                # redis error is terminal, invoke ai directly
                asyncio.create_task(
                    notice_ai(notice_payload, redis_res.get("messages"), invoke=True)
                )
                return redis_res

            # redis always returns updated task_info
            task_info = redis_res.get("messages")
            status = task_info.get("status")

            logger.info(f"[DataExecutors][update_task] Get task info in redis: {task_info}.")

            notice_payload = construct_notice_payload(
                task_id=task_info.get("task_id"),
                user_uid=task_info.get("client_id"),
                conversation_uid=task_info.get("history_id"),
                status=status,
                result=task_info.get("result"),
                payload=task_info.get("payload"),
            )

            # 2. finished task -> persist to mysql and invoke ai
            if status in TASK_FINISHING_STATUS:
                mysql_payload = {
                    "task_id": task_info["task_id"],
                    "status": status,
                    "result": task_info.get("result", []),
                }

                result = await self.mysql.update_task_result(mysql_payload)
                asyncio.create_task(
                    notice_ai(notice_payload, 'Task finished.', invoke=True)
                )
                return result

            # 3. running / pending -> only notice, do not invoke ai
            asyncio.create_task(
                notice_ai(notice_payload, 'Task status updated.', invoke=False)
            )
            return redis_res

        except Exception as e:
            logger.exception(f"[DataExecutors][update_task] error: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    @task_handler("kill_task")
    async def kill_task(self, payload: dict) -> dict:
        """
        Manual kill a task.

        Workflow:
        1. Try to expire redis key (fast path)
        2. Persist manual stopped state to MySQL (source of truth)
        3. Notify AI asynchronously
        """
        try:
            logger.info("[DataExecutors][kill_task] enter.")

            redis_res = await self.redis.expire_immediately(payload)

            # Decide task_id source and notice behavior
            if redis_res.get("success") and isinstance(redis_res.get("messages"), dict):
                # Task was running in redis
                task_info = redis_res["messages"]
                task_id = task_info["task_id"]
                result_list = task_info.get("result", [])
                invoke_notice = True
                finished_at = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
                return_payload = "mysql"
            else:
                # Task not found / already finished / redis failure
                task_id = payload["task_id"]
                result_list = []
                invoke_notice = False
                finished_at = None
                return_payload = "redis"

            # Persist manual stopped state to MySQL
            mysql_payload = {
                "task_id": task_id,
                "status": "manual stopped",
                "result": result_list,
            }
            if finished_at:
                mysql_payload["finished_at"] = finished_at

            mysql_res = await self.mysql.update_task_result(mysql_payload)
            messages = mysql_res.get("messages")

            # Build and send notice asynchronously
            notice_payload = construct_notice_payload(
                task_id=messages.get("task_id"),
                user_uid=messages.get("user_uid"),
                conversation_uid=messages.get("conversation_uid"),
                status=messages.get("status"),
                result=messages.get("result"),
                payload=messages.get("payload"),
            )
            asyncio.create_task(
                notice_ai(notice_payload, "Task canceled by user.", invoke=invoke_notice)
            )

            # Keep original return semantics
            return mysql_res if return_payload == "mysql" else redis_res

        except Exception as e:
            logger.exception(f"[DataExecutors][kill_task] error: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    @task_handler("get_task_info")
    async def get_task_info(self, payload: dict) -> dict:
        """
        Get task info.

        Workflow:
        1. Query Redis (running task)
        2. If not found, query MySQL (finished task)
        """
        try:
            logger.info("[DataExecutors][get_task_info] enter.")
            redis_res = await self.redis.get_task_info(payload)
            if redis_res.get("success"):
                return redis_res

            # Redis miss -> query MySQL
            if "task_id" not in payload:
                return redis_res

            return await self.mysql.fetch_task_info(payload)

        except Exception as e:
            logger.exception(
                f"[DataExecutors][get_task_info] error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    # --------------------------------------------------
    # Lingterm Memory
    # --------------------------------------------------
    @task_handler("fetch_longterm_memory")
    async def fetch_longterm_memory(self, payload: dict) -> dict:
        """
        Fetch longterm memory for a user.

        Workflow:
        1. Try fetch from Redis
        2. On Redis miss, fetch from MySQL
        3. Backfill Redis with MySQL result (best effort)
        """
        try:
            logger.info("[DataExecutors][fetch_longterm_memory] enter.")

            # 1. Try Redis first
            redis_res = await self.redis.fetch_longterm_memory(payload)
            if redis_res.get("success") and redis_res.get("cache_hit"):
                return redis_res

            # 2. Redis miss -> fetch from MySQL
            mysql_res = await self.mysql.fetch_longterm_memory(payload)
            if not mysql_res.get("success"):
                return mysql_res

            messages = mysql_res.get("messages", [])

            # 3. Backfill Redis (best effort, ignore failure)
            try:
                backfill_payload = {
                    "client_id": payload["client_id"],
                    "messages": messages,
                }
                await self.redis.backfill_longterm_memory(backfill_payload)
            except Exception as e:
                logger.warning(
                    f"[DataExecutors][fetch_longterm_memory] Redis backfill failed: {e}"
                )

            return mysql_res

        except Exception as e:
            logger.exception(
                f"[DataExecutors][fetch_longterm_memory] error: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
            
    @task_handler("update_longterm_memory")
    async def update_longterm_memory(self, payload: dict) -> dict:
        """
        Update longterm memory.

        Workflow:
        1. Update MySQL (source of truth)
        2. Expire Redis cache if exists (best effort)
        """
        try:
            logger.info("[DataExecutors][update_longterm_memory] enter.")

            # 1. Update MySQL first (authoritative)
            mysql_res = await self.mysql.update_longterm_memory(payload)
            if not mysql_res.get("success"):
                return mysql_res

            # 2. Best-effort expire Redis
            try:
                expire_payload = {
                    "client_id": payload["client_id"],
                    "messages": mysql_res.get("messages", {}),
                }
                await self.redis.expire_longterm_memory(expire_payload)
            except Exception as e:
                # Redis failure must NOT affect MySQL result
                logger.warning(
                    f"[DataExecutors][update_longterm_memory] Redis expire failed: {e}"
                )

            return mysql_res

        except Exception as e:
            logger.exception(
                f"[DataExecutors][update_longterm_memory] error: {e}"
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