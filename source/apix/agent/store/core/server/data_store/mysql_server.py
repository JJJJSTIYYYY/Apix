import asyncio
import re
import json
import time
from pathlib import Path

try:
    import aiomysql
    from aiomysql.cursors import DictCursor
except ImportError as exc:
    raise ImportError(
        "MySQl store requires the `aiomysql` package. Run `uv add aiomysql` to install."
    ) from exc
from fastapi.encoders import jsonable_encoder

from apix.agent.store.core.server.data_store.data_server_base import DataServerBase
from apix.agent.store.core.server.data_store.utils import data_store_handler
from apix.common.lifespan.auto_init import auto_init
from apix.config.base_config import MYSQL_BASE_URL, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE, MYSQL_CHARSET, AUTO_COMMIT
from apix.common.utils.logger import logger


def _split_mysql_script(script: str) -> list[str]:
    """Split a MySQL script while honoring client-side DELIMITER commands."""
    delimiter = ";"
    buffer: list[str] = []
    statements: list[str] = []

    for line in script.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("DELIMITER "):
            if any(part.strip() for part in buffer):
                raise ValueError("DELIMITER changed before the SQL statement ended")
            delimiter = stripped.split(maxsplit=1)[1]
            if not delimiter:
                raise ValueError("DELIMITER must not be empty")
            continue

        if not buffer and not stripped:
            continue

        buffer.append(line)
        candidate = "\n".join(buffer).rstrip()
        if candidate.endswith(delimiter):
            statement = candidate[:-len(delimiter)].strip()
            if statement:
                statements.append(statement)
            buffer.clear()

    if any(part.strip() for part in buffer):
        raise ValueError("MySQL initialization script has an incomplete statement")

    return statements


def _identity_failure(exc: Exception) -> dict:
    return {
        "success": False,
        "messages": {
            "msg": f"{type(exc).__name__}: {exc}",
            "uid": None,
        },
    }


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
        self._schema_path = Path(__file__).with_name("init_mysql.sql")
        

    async def start(self):
        """Initialize the pool and create missing schema objects."""
        async with self._pool_lock:
            if self._pool is not None:
                return

            pool = await aiomysql.create_pool(**self._pool_args)
            try:
                await self._initialize_database(pool)
            except Exception:
                pool.close()
                await pool.wait_closed()
                raise
            self._pool = pool


    async def _initialize_database(self, pool) -> None:
        schema = self._schema_path.read_text(encoding="utf-8")
        statements = _split_mysql_script(schema)

        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                for statement in statements:
                    await cursor.execute(statement)


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

    @data_store_handler(failure_factory=_identity_failure)
    async def create_a_user(self, payload: dict) -> dict:
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
        

    @data_store_handler(failure_factory=_identity_failure)
    async def verify_user(self, payload: dict) -> dict:
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
        

    @data_store_handler
    async def ensure_user_exists(self, payload: dict, exist: bool = True) -> dict:
        user_uid = payload["user_uid"]
        user_name = payload.get("username")
        res = await self._call_procedure("ensure_user_exists", (user_uid, user_name))
        if exist and len(res) == 0: raise Exception("User do not exist.")
        elif not exist and len(res) > 0: raise Exception("User has already exist.")
        return {
            "success": True,
            "messages": "success",
        }

    # --------------------------------------------------
    # Conversation
    # --------------------------------------------------

    @data_store_handler
    async def fetch_conversation_list(self, payload: dict) -> dict:
        user_uid = payload["user_uid"]
        rows = await self._call_procedure("fetch_conversation_list", (str(user_uid),))
        return {
            "success": True,
            "messages": rows,
        }
        

    @data_store_handler
    async def get_conversation_meta_by_id(self, payload: dict) -> dict:
        conversation_uid = payload["conversation_uid"]
        rows = await self._call_procedure("get_conversation_meta_by_id", (conversation_uid,))
        return {
            "success": True,
            "messages": rows,
        }
        

    @data_store_handler
    async def create_conversation(self, payload: dict) -> dict:
        user_uid = payload["user_uid"]
        platform = payload.get("platform", "default")
        conversation_uid = self._conversation_id_generator()
        title = payload.get("title", "New Conversation...")
        workspace = payload.get("workspace", None)
        is_cron = payload.get("is_cron", False)

        await self._call_procedure("create_conversation", (user_uid, platform, conversation_uid, title, workspace, is_cron))
        return {
            "success": True,
            "messages": {"conversation_uid": conversation_uid},
        }
        

    @data_store_handler
    async def update_conversation(self, payload: dict) -> dict:
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
            "messages": "success",
        }

    # --------------------------------------------------
    # Messages
    # --------------------------------------------------

    @data_store_handler
    async def append_message(self, payload: dict) -> dict:
        user_uid = payload["user_uid"]
        conversation_uid = payload["conversation_uid"]
        message = payload["message"]
        
        if not message:
            raise ValueError("Messages is empty")
        
        message_uid = message["message_uid"]
        role = message["role"]
        name = message.get("name")
        content = message["content"]
        metadata = message.get("metadata", {})
        extensions = message.get("extensions", {})
        generation_id = message.get("generation_id", "")
        node_id = message.get("node_id", "")
        parent_id = message.get("parent_id", "")

        if metadata is None:
            metadata = {}
        if not isinstance(metadata, str):
            metadata = json.dumps(metadata, ensure_ascii=False)

        if extensions is None:
            extensions = {}
        if not isinstance(extensions, str):
            extensions = json.dumps(extensions, ensure_ascii=False)

        result = await self._call_procedure(
            "append_message", 
            (
                user_uid,
                conversation_uid,
                message_uid,
                role,
                name,
                content,
                metadata,
                extensions,
                generation_id,
                node_id,
                parent_id,
            )
        )
        cursor =  result[0].get("msg_cursor", -1)
        timestamp = result[0].get("timestamp")
        if cursor == -1: raise ValueError("Invalid cursor the database returned.")
        return {
            "success": True,
            "messages": {
                "msg_cursor": cursor,
                "timestamp": timestamp,
            }
        }
        

    @data_store_handler
    async def delete_messages(self, payload: dict) -> dict:
        user_uid = payload["user_uid"]
        conversation_uid = payload["conversation_uid"]
        messages = payload["messages"]
        
        if not messages:
            raise ValueError("Messages list is empty")
            
        message_uids = []
        for node_id in messages:
            res = await self._call_procedure("delete_messages_node", (user_uid, conversation_uid, node_id))
            for row in res:
                if not isinstance(row, dict):
                    continue
                message_uid = row.get("message_uid")
                if message_uid:
                    message_uids.append({"message_uid": message_uid})
        
        return {
            "success": True,
            "messages": message_uids,
        }
        

    @data_store_handler
    async def fetch_messages_after_cursor(self, payload: dict) -> dict:
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
        
        
    @data_store_handler
    async def search_messages_by_keyword(self, payload: dict) -> dict:
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

        
    # --------------------------------------------------
    # Skills (meta only)
    # --------------------------------------------------

    @data_store_handler
    async def insert_skill_info(self, payload: dict) -> dict:
        user_uid = payload["user_uid"]
        skill_info_list = payload.get("skills", [])

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

        

    @data_store_handler
    async def update_skill_status(self, payload: dict) -> dict:
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

        
        
    @data_store_handler
    async def fetch_available_skills(self, payload: dict) -> dict:
        user_uid = payload["user_uid"]
        limit = payload.get("limit", 5)

        rows = await self._call_procedure("fetch_agent_skills", (user_uid, limit,))

        return {
            "success": True,
            "messages": rows,
        }

        

    @data_store_handler
    async def fetch_target_skill(self, payload: dict) -> dict:
        user_uid = payload["user_uid"]
        skill_id = payload["skill_id"]
        rows = await self._call_procedure(
            "fetch_target_skill",
            (user_uid, skill_id,),
        )
        return {
            "success": True,
            "messages": rows,
        }
        
    # --------------------------------------------------
    # Short-term Memory 
    # --------------------------------------------------

    @data_store_handler
    async def fetch_shortterm_memory(self, payload: dict) -> dict:
        user_uid = payload["user_uid"]
        conversation_uid = payload["conversation_uid"]
        rows = await self._call_procedure("fetch_shortterm_memory", (user_uid, conversation_uid))
        return {
            "success": True,
            "messages": rows,
        }
        

    @data_store_handler
    async def insert_shortterm_memory(self, payload: dict) -> dict:
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
        

    @data_store_handler
    async def delete_shortterm_memory(self, payload: dict) -> dict:
        memory_ids = payload["memory_ids"]
        user_uid = payload["user_uid"]
        conversation_uid = payload["conversation_uid"]
        await self._call_procedure("delete_shortterm_memory", (json.dumps(memory_ids), user_uid, conversation_uid))
        return {
            "success": True,
            "messages": "success",
        }

    # --------------------------------------------------
    # Long-term Memory
    # --------------------------------------------------

    @data_store_handler
    async def fetch_longterm_memory(self, payload: dict) -> dict:
        user_uid = payload["user_uid"]
        rows = await self._call_procedure("fetch_longterm_memory", (user_uid,))
        return {
            "success": True, 
            "messages": rows
        }

    @data_store_handler
    async def insert_longterm_memory(self, payload: dict) -> dict:
        memory_id = payload["memory_id"]
        user_uid = payload["user_uid"]
        title = payload["title"]
        date = payload["date"]
        content = payload["content"]
        source = payload["source"]
        await self._call_procedure(
            "insert_longterm_memory",
            (memory_id, user_uid, title, date, content, source),
        )
        return {
            "success": True, 
            "messages": {
                "memory_id": memory_id
            }
        }

    @data_store_handler
    async def update_longterm_memory(self, payload: dict) -> dict:
        memory_id = payload["memory_id"]
        user_uid = payload["user_uid"]
        title = payload.get("title")
        date = payload.get("date")
        content = payload.get("content")
        source = payload.get("source")
        is_deleted = payload.get("is_deleted")
        await self._call_procedure(
            "update_longterm_memory",
            (memory_id, user_uid, title, date, content, source, is_deleted),
        )
        return {"success": True, "messages": "success"}
        
    # --------------------------------------------------
    # Custom Provider 
    # --------------------------------------------------

    @data_store_handler
    async def create_llm_provider(self, payload: dict) -> dict:
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
        

    @data_store_handler
    async def get_llm_providers(self, payload: dict) -> dict:
        user_uid = payload["user_uid"]
        rows = await self._call_procedure("get_llm_providers", (user_uid, ))
        return {
            "success": True,
            "messages": rows,
        }
        

    @data_store_handler
    async def get_llm_provider_by_id(self, payload: dict) -> dict:
        provider_id = payload["provider_id"]
        rows = await self._call_procedure("get_llm_provider_by_id", (provider_id, ))
        return {
            "success": True,
            "messages": rows,
        }
        

    @data_store_handler
    async def update_llm_provider(self, payload: dict) -> dict:
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
        
    # --------------------------------------------------
    # MCP Server
    # --------------------------------------------------

    @data_store_handler
    async def create_mcp_server(self, payload: dict) -> dict:
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



    @data_store_handler
    async def get_mcp_servers(self, payload: dict) -> dict:
        user_uid = payload["user_uid"]
        rows = await self._call_procedure("get_mcp_servers", (user_uid,),)
        return {
            "success": True,
            "messages": rows,
        }



    @data_store_handler
    async def get_enabled_mcp_servers(self, payload: dict) -> dict:
        user_uid = payload["user_uid"]
        rows = await self._call_procedure("get_enabled_mcp_servers", (user_uid,),)
        return {
            "success": True,
            "messages": rows,
        }



    @data_store_handler
    async def update_mcp_server(self, payload: dict) -> dict:
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

        
    # --------------------------------------------------
    # Cron task
    # --------------------------------------------------

    @data_store_handler
    async def create_cron_task(self, payload: dict) -> dict:
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

        

    @data_store_handler
    async def get_all_enabled_cron_tasks(self, payload: dict) -> dict:
        rows = await self._call_procedure("get_all_enabled_cron_tasks", (),)
        return {
            "success": True,
            "messages": rows,
        }

        

    @data_store_handler
    async def get_cron_tasks(self, payload: dict) -> dict:
        user_uid = payload["user_uid"]
        rows = await self._call_procedure("get_cron_tasks", (user_uid,),)
        return {
            "success": True,
            "messages": rows,
        }

        

    @data_store_handler
    async def get_cron_task_by_id(self, payload: dict) -> dict:
        task_id = payload["task_id"]
        rows = await self._call_procedure("get_cron_task_by_id", (task_id,),)
        return {
            "success": True,
            "messages": rows,
        }

        
        
    @data_store_handler
    async def update_cron_task(self, payload: dict) -> dict:
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




data_server = MysqlService(
    host=MYSQL_BASE_URL,
    port=MYSQL_PORT,
    user=MYSQL_USER,
    password=MYSQL_PASSWORD,
    database=MYSQL_DATABASE,
    charset=MYSQL_CHARSET,
)
auto_init.register(data_server)
