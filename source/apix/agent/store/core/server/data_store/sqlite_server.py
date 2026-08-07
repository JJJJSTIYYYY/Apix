import asyncio
import json
import re
import sqlite3
import time
from functools import wraps
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional, TypeVar, cast

from apix.agent.store.core.server.data_store.data_server_base import DataServerBase
from apix.common.lifespan.auto_init import auto_init
from apix.common.utils.logger import logger
from apix.config.base_config import SQLITE_DATABASE


T = TypeVar("T")
TaskHandler = TypeVar(
    "TaskHandler",
    bound=Callable[..., Awaitable[dict]],
)
FailureFactory = Callable[[Exception], dict]


def _identity_failure(exc: Exception) -> dict:
    return {
        "success": False,
        "messages": {
            "msg": f"{type(exc).__name__}: {exc}",
            "uid": None,
        },
    }


def data_store_handler(
    func: TaskHandler | None = None,
    *,
    failure_factory: FailureFactory | None = None,
) -> TaskHandler | Callable[[TaskHandler], TaskHandler]:
    """Normalize unhandled failures from public data-store methods."""

    def decorator(handler: TaskHandler) -> TaskHandler:
        @wraps(handler)
        async def wrapper(*args, **kwargs) -> dict:
            logger.trace()
            try:
                return await handler(*args, **kwargs)
            except Exception as exc:
                logger.exception(
                    f"Data-store handler `{handler.__name__}` failed: {exc}"
                )
                if failure_factory is not None:
                    return failure_factory(exc)
                return {
                    "success": False,
                    "messages": f"fail: {exc}",
                }

        return cast(TaskHandler, wrapper)

    if func is None:
        return decorator
    return decorator(func)


class SqliteService(DataServerBase):
    """SQLite-backed replacement for :class:`MysqlService`.

    A single connection is shared by the service. SQLite calls run in a worker
    thread and are serialized with an asyncio lock, so synchronous sqlite3 I/O
    never blocks the event loop and one connection is never used concurrently.
    """

    def __init__(self, db_path: Optional[str | Path] = None):
        default_path = SQLITE_DATABASE
        selected_path = str(db_path if db_path is not None else default_path)
        self._db_path = (
            selected_path
            if selected_path == ":memory:"
            else str(Path(selected_path).expanduser())
        )
        self._connection: Optional[sqlite3.Connection] = None
        self._connection_lock = asyncio.Lock()
        self._schema_path = Path(__file__).with_name("init_sqlite.sql")

    async def start(self):
        """Open the database and create missing tables/indexes."""
        async with self._connection_lock:
            if self._connection is not None:
                return

            if self._db_path != ":memory:":
                Path(self._db_path).expanduser().resolve().parent.mkdir(
                    parents=True, exist_ok=True
                )
            schema = self._schema_path.read_text(encoding="utf-8")

            def open_database() -> sqlite3.Connection:
                connection = sqlite3.connect(
                    self._db_path,
                    timeout=30,
                    check_same_thread=False,
                )
                try:
                    connection.row_factory = sqlite3.Row
                    connection.execute("PRAGMA foreign_keys = ON")
                    connection.execute("PRAGMA busy_timeout = 30000")
                    connection.execute("PRAGMA journal_mode = WAL")
                    connection.executescript(schema)
                    connection.commit()
                    return connection
                except Exception:
                    connection.close()
                    raise

            self._connection = await asyncio.to_thread(open_database)

    async def stop(self):
        """Commit pending work and close the database connection."""
        async with self._connection_lock:
            connection = self._connection
            if connection is None:
                return
            self._connection = None

            def close_database() -> None:
                connection.commit()
                connection.close()

            await asyncio.to_thread(close_database)

    async def _run(self, operation: Callable[[sqlite3.Connection], T]) -> T:
        async with self._connection_lock:
            connection = self._connection
            if connection is None:
                raise RuntimeError(
                    "SQLite database is not initialized, call start() first"
                )

            def run_operation() -> T:
                try:
                    result = operation(connection)
                    connection.commit()
                    return result
                except Exception:
                    connection.rollback()
                    raise

            return await asyncio.to_thread(run_operation)

    async def _execute(self, sql: str, params: tuple[Any, ...] = ()) -> int:
        def operation(connection: sqlite3.Connection) -> int:
            return connection.execute(sql, params).rowcount

        return await self._run(operation)

    async def _executemany(
        self, sql: str, params: list[tuple[Any, ...]]
    ) -> int:
        def operation(connection: sqlite3.Connection) -> int:
            return connection.executemany(sql, params).rowcount

        return await self._run(operation)

    async def _fetch_all(
        self, sql: str, params: tuple[Any, ...] = ()
    ) -> list[dict[str, Any]]:
        def operation(connection: sqlite3.Connection) -> list[dict[str, Any]]:
            return [
                self._normalize_row(dict(row))
                for row in connection.execute(sql, params).fetchall()
            ]

        return await self._run(operation)

    @staticmethod
    def _json(value: Any, default: Any) -> str:
        if value is None:
            value = default
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
        """Match jsonable_encoder's ISO formatting for MySQL datetimes."""
        for key, value in row.items():
            if not isinstance(value, str):
                continue
            if key.endswith("_at") or key in {"exec_time", "timestamp"}:
                if re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", value):
                    row[key] = value.replace(" ", "T", 1)
        return row

    # --------------------------------------------------
    # Users
    # --------------------------------------------------

    @data_store_handler(failure_factory=_identity_failure)
    async def create_a_user(self, payload: dict) -> dict:
        user_uid = payload["user_uid"]
        await self._execute(
            "INSERT INTO users (user_uid, username, password) VALUES (?, ?, ?)",
            (user_uid, payload["username"], payload["password"]),
        )
        return {
            "success": True,
            "messages": {"msg": "success", "uid": user_uid},
        }

    @data_store_handler(failure_factory=_identity_failure)
    async def verify_user(self, payload: dict) -> dict:
        rows = await self._fetch_all(
            "SELECT user_uid, username FROM users "
            "WHERE username = ? AND password = ?",
            (payload["username"], payload["password"]),
        )
        if len(rows) != 1:
            raise Exception("User do not exist or wrong password.")
        return {
            "success": True,
            "messages": {"msg": "success", "uid": rows[0]["user_uid"]},
        }

    @data_store_handler
    async def ensure_user_exists(self, payload: dict, exist: bool = True) -> dict:
        rows = await self._fetch_all(
            "SELECT user_uid, username FROM users "
            "WHERE user_uid = ? OR username = ?",
            (payload["user_uid"], payload.get("username")),
        )
        if exist and not rows:
            raise Exception("User do not exist.")
        if not exist and rows:
            raise Exception("User has already exist.")
        return {"success": True, "messages": "success"}

    # --------------------------------------------------
    # Conversations
    # --------------------------------------------------

    @data_store_handler
    async def fetch_conversation_list(self, payload: dict) -> dict:
        rows = await self._fetch_all(
            """
            SELECT conversation_uid, title, work_space, last_active_at,
                   created_at, latest_cursor, is_pinned, has_new_message,
                   is_cron
            FROM conversations
            WHERE user_uid = ? AND is_deleted != 1
            ORDER BY is_pinned DESC, last_active_at DESC
            """,
            (str(payload["user_uid"]),),
        )
        return {"success": True, "messages": rows}

    @data_store_handler
    async def get_conversation_meta_by_id(self, payload: dict) -> dict:
        rows = await self._fetch_all(
            """
            SELECT conversation_uid, title, work_space, last_active_at,
                   created_at, latest_cursor, is_pinned, has_new_message
            FROM conversations
            WHERE conversation_uid = ? AND is_deleted != 1
            LIMIT 1
            """,
            (payload["conversation_uid"],),
        )
        return {"success": True, "messages": rows}

    @data_store_handler
    async def create_conversation(self, payload: dict) -> dict:
        conversation_uid = self._conversation_id_generator()
        await self._execute(
            """
            INSERT INTO conversations (
                user_uid, platform, conversation_uid, title, work_space,
                last_active_at, latest_cursor, is_cron
            ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 0, ?)
            """,
            (
                payload["user_uid"],
                payload.get("platform", "default"),
                conversation_uid,
                (
                    "New Conversation..."
                    if payload.get("title") is None
                    else payload["title"]
                ),
                payload.get("workspace") or "",
                payload.get("is_cron", False),
            ),
        )
        return {"success": True, "messages": {"conversation_uid": conversation_uid}}

    @data_store_handler
    async def update_conversation(self, payload: dict) -> dict:
        conversation_uid = payload["conversation_uid"]
        await self._execute(
            """
            UPDATE conversations
            SET title = COALESCE(?, title),
                work_space = COALESCE(?, work_space),
                is_pinned = COALESCE(?, is_pinned),
                is_deleted = COALESCE(?, is_deleted),
                has_new_message = COALESCE(?, has_new_message)
            WHERE user_uid = ? AND conversation_uid = ?
            """,
            (
                payload.get("title"),
                payload.get("workspace"),
                payload.get("is_pinned"),
                payload.get("is_deleted"),
                payload.get("has_new_message"),
                payload["user_uid"],
                conversation_uid,
            ),
        )
        return {"success": True, "messages": "success"}

    # --------------------------------------------------
    # Messages
    # --------------------------------------------------

    @data_store_handler
    async def append_message(self, payload: dict) -> dict:
        user_uid = payload["user_uid"]
        conversation_uid = payload["conversation_uid"]
        message = payload["message"]
        if not message:
            raise ValueError("Messages list is empty")

        role = message["role"]
        metadata = self._json(message.get("metadata"), {})
        extensions = self._json(message.get("extensions"), {})

        def operation(connection: sqlite3.Connection) -> dict[str, Any]:
            connection.execute("BEGIN IMMEDIATE")
            conversation = connection.execute(
                """
                SELECT id, latest_cursor
                FROM conversations
                WHERE user_uid = ? AND conversation_uid = ?
                  AND is_deleted = 0
                """,
                (user_uid, conversation_uid),
            ).fetchone()
            if conversation is None:
                raise RuntimeError("Conversation not found or deleted")

            cursor = int(conversation["latest_cursor"]) + 1
            insert_cursor = connection.execute(
                """
                INSERT INTO messages (
                    message_uid, msg_cursor, user_uid, conversation_id,
                    conversation_uid, generation_id, node_id, parent_id,
                    role, name, content, metadata, extensions
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message["message_uid"],
                    cursor,
                    user_uid,
                    conversation["id"],
                    conversation_uid,
                    message.get("generation_id", ""),
                    message.get("node_id", ""),
                    message.get("parent_id", ""),
                    role,
                    message.get("name"),
                    message["content"],
                    metadata,
                    extensions,
                ),
            )
            connection.execute(
                """
                UPDATE conversations
                SET latest_cursor = ?,
                    last_active_at = CURRENT_TIMESTAMP,
                    has_new_message = ?
                WHERE id = ?
                """,
                (
                    cursor,
                    0 if role == "user" else 1,
                    conversation["id"],
                ),
            )
            created = connection.execute(
                "SELECT timestamp FROM messages WHERE id = ?",
                (insert_cursor.lastrowid,),
            ).fetchone()
            result = {
                "msg_cursor": cursor,
                "timestamp": created["timestamp"],
            }
            return self._normalize_row(result)

        result = await self._run(operation)
        return {"success": True, "messages": result}

    @data_store_handler
    async def delete_messages(self, payload: dict) -> dict:
        node_ids = payload["messages"]
        if not node_ids:
            raise ValueError("Messages list is empty")
        user_uid = payload["user_uid"]
        conversation_uid = payload["conversation_uid"]

        def operation(connection: sqlite3.Connection) -> list[dict]:
            result: list[dict] = []
            for node_id in node_ids:
                rows = connection.execute(
                    """
                    SELECT id, message_uid FROM messages
                    WHERE user_uid = ? AND conversation_uid = ? AND node_id = ?
                    """,
                    (user_uid, conversation_uid, node_id),
                ).fetchall()
                if rows:
                    connection.executemany(
                        "UPDATE messages SET is_deleted = 1 WHERE id = ?",
                        [(row["id"],) for row in rows],
                    )
                result.extend(
                    {"message_uid": row["message_uid"]}
                    for row in rows
                    if row["message_uid"]
                )
            return result

        return {"success": True, "messages": await self._run(operation)}

    @data_store_handler
    async def fetch_messages_after_cursor(self, payload: dict) -> dict:
        after_cursor = max(int(payload.get("cursor", 0)), 0)
        limit = int(payload.get("limit", 65535))
        rows = await self._fetch_all(
            """
            SELECT message_uid, msg_cursor, role, name, content, metadata,
                   extensions, timestamp, generation_id, node_id, parent_id,
                   is_deleted
            FROM messages
            WHERE user_uid = ? AND conversation_uid = ? AND msg_cursor >= ?
            ORDER BY msg_cursor ASC
            LIMIT ?
            """,
            (
                payload["user_uid"],
                payload["conversation_uid"],
                after_cursor,
                limit,
            ),
        )
        next_cursor = rows[-1]["msg_cursor"] + 1 if rows else after_cursor
        return {
            "success": True,
            "messages": rows,
            "next_cursor": next_cursor,
        }

    @data_store_handler
    async def search_messages_by_keyword(self, payload: dict) -> dict:
        keyword = payload["keyword"]
        if not re.sub(r"[%_\\\s]+", "", keyword):
            return {"success": True, "messages": []}
        keyword = re.sub(r"[_\\\s]+", "%", keyword)
        keyword = re.sub(r"%+", "%", keyword).strip("%")
        rows = await self._fetch_all(
            """
            SELECT m.conversation_uid, m.generation_id, m.role, m.content,
                   c.title, c.last_active_at
            FROM messages AS m
            JOIN conversations AS c ON c.id = m.conversation_id
            WHERE c.user_uid = ? AND c.is_deleted = 0
              AND m.is_deleted = 0 AND m.role IN ('user', 'ai')
              AND m.content LIKE ?
            ORDER BY c.last_active_at DESC, m.id DESC
            LIMIT 300
            """,
            (payload["user_uid"], f"%{keyword}%"),
        )
        return {"success": True, "messages": rows}

    # --------------------------------------------------
    # Skills
    # --------------------------------------------------

    @data_store_handler
    async def insert_skill_info(self, payload: dict) -> dict:
        user_uid = payload["user_uid"]
        params = []
        for skill in payload.get("skills", []):
            params.append(
                (
                    skill["skill_id"],
                    skill["skill_name"],
                    skill["skill_description"],
                    skill.get("skill_version", "v1.0"),
                    skill["package_path"],
                    skill["package_size"],
                    skill.get("package_sha256"),
                    user_uid,
                )
            )
        if params:
            await self._executemany(
                """
                INSERT INTO agent_skills (
                    skill_id, skill_name, skill_description, skill_version,
                    package_path, package_size, package_sha256, user_uid
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                params,
            )
        return {"success": True, "messages": "success"}

    @data_store_handler
    async def update_skill_status(self, payload: dict) -> dict:
        await self._execute(
            """
            UPDATE agent_skills
            SET is_active = COALESCE(?, is_active),
                deleted = COALESCE(?, deleted),
                deleted_at = CASE WHEN ? = 1 THEN CURRENT_TIMESTAMP
                                  ELSE deleted_at END
            WHERE skill_id = ? AND user_uid = ? AND deleted = 0
            """,
            (
                payload.get("is_active"),
                payload.get("deleted"),
                payload.get("deleted"),
                payload["skill_id"],
                payload["user_uid"],
            ),
        )
        return {"success": True, "messages": "success"}

    @data_store_handler
    async def fetch_available_skills(self, payload: dict) -> dict:
        rows = await self._fetch_all(
            """
            SELECT skill_id, skill_name, skill_description, skill_version,
                   package_path, package_size, is_active, upload_at
            FROM agent_skills
            WHERE user_uid = ? AND deleted = 0
            ORDER BY upload_at DESC
            LIMIT ?
            """,
            (payload["user_uid"], int(payload.get("limit", 5))),
        )
        return {"success": True, "messages": rows}

    @data_store_handler
    async def fetch_target_skill(self, payload: dict) -> dict:
        rows = await self._fetch_all(
            """
            SELECT skill_id, skill_name, skill_description, skill_version,
                   package_path, package_size, is_active, upload_at,
                   deleted, deleted_at
            FROM agent_skills
            WHERE user_uid = ? AND skill_id = ? AND deleted = 0
            LIMIT 1
            """,
            (payload["user_uid"], payload["skill_id"]),
        )
        return {"success": True, "messages": rows}

    # --------------------------------------------------
    # Short-term memory
    # --------------------------------------------------

    @data_store_handler
    async def fetch_shortterm_memory(self, payload: dict) -> dict:
        rows = await self._fetch_all(
            """
            SELECT memory_id, content, created_timestamp
            FROM shortterm_memory
            WHERE user_uid = ? AND conversation_uid = ? AND is_deleted = 0
            ORDER BY created_timestamp DESC
            LIMIT 1
            """,
            (payload["user_uid"], payload["conversation_uid"]),
        )
        return {"success": True, "messages": rows}

    @data_store_handler
    async def insert_shortterm_memory(self, payload: dict) -> dict:
        await self._execute(
            """
            INSERT INTO shortterm_memory (
                memory_id, user_uid, conversation_uid, content,
                created_timestamp
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                payload["memory_id"],
                payload["user_uid"],
                payload["conversation_uid"],
                payload["content"],
                int(time.time() * 1_000_000),
            ),
        )
        return {"success": True, "messages": "success"}

    @data_store_handler
    async def delete_shortterm_memory(self, payload: dict) -> dict:
        memory_ids = payload["memory_ids"]
        if memory_ids:
            placeholders = ", ".join("?" for _ in memory_ids)
            await self._execute(
                f"""
                UPDATE shortterm_memory SET is_deleted = 1
                WHERE user_uid = ? AND conversation_uid = ?
                  AND is_deleted = 0 AND memory_id IN ({placeholders})
                """,
                (
                    payload["user_uid"],
                    payload["conversation_uid"],
                    *memory_ids,
                ),
            )
        return {"success": True, "messages": "success"}

    # --------------------------------------------------
    # Long-term memory
    # --------------------------------------------------

    @data_store_handler
    async def fetch_longterm_memory(self, payload: dict) -> dict:
        rows = await self._fetch_all(
            """
            SELECT memory_id, title, memory_date AS date, content, source
            FROM longterm_memory
            WHERE user_uid = ? AND is_deleted = 0
            ORDER BY memory_date DESC, id DESC
            """,
            (payload["user_uid"],),
        )
        return {"success": True, "messages": rows}

    @data_store_handler
    async def insert_longterm_memory(self, payload: dict) -> dict:
        memory_id = payload["memory_id"]
        await self._execute(
            """
            INSERT INTO longterm_memory (
                memory_id, user_uid, title, memory_date, content, source
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                memory_id,
                payload["user_uid"],
                payload["title"],
                payload["date"],
                payload["content"],
                payload["source"],
            ),
        )
        return {"success": True, "messages": {"memory_id": memory_id}}

    @data_store_handler
    async def update_longterm_memory(self, payload: dict) -> dict:
        is_deleted = payload.get("is_deleted")
        await self._execute(
            """
            UPDATE longterm_memory
            SET title = COALESCE(?, title),
                memory_date = COALESCE(?, memory_date),
                content = COALESCE(?, content),
                source = COALESCE(?, source),
                is_deleted = COALESCE(?, is_deleted),
                deleted_at = CASE
                    WHEN ? = 1 THEN CURRENT_TIMESTAMP
                    ELSE deleted_at
                END,
                updated_at = CURRENT_TIMESTAMP
            WHERE memory_id = ? AND user_uid = ? AND is_deleted = 0
            """,
            (
                payload.get("title"),
                payload.get("date"),
                payload.get("content"),
                payload.get("source"),
                is_deleted,
                is_deleted,
                payload["memory_id"],
                payload["user_uid"],
            ),
        )
        return {"success": True, "messages": "success"}

    # --------------------------------------------------
    # LLM providers
    # --------------------------------------------------

    @data_store_handler
    async def create_llm_provider(self, payload: dict) -> dict:
        provider_id = payload["provider_id"]
        await self._execute(
            """
            INSERT INTO llm_provider (
                provider_id, user_uid, provider_name, type, endpoint,
                model_list, description
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                provider_id,
                payload["user_uid"],
                payload["provider_name"],
                (payload.get("type", "openai") or "openai").lower(),
                payload["endpoint"],
                json.dumps(payload["model_list"]),
                payload.get("description"),
            ),
        )
        return {"success": True, "messages": {"provider_id": provider_id}}

    @data_store_handler
    async def get_llm_providers(self, payload: dict) -> dict:
        rows = await self._fetch_all(
            """
            SELECT provider_id, provider_name, type, endpoint, model_list,
                   description, created_at
            FROM llm_provider
            WHERE user_uid = ? AND is_deleted = 0
            ORDER BY created_at DESC
            """,
            (payload["user_uid"],),
        )
        return {"success": True, "messages": rows}

    @data_store_handler
    async def get_llm_provider_by_id(self, payload: dict) -> dict:
        rows = await self._fetch_all(
            """
            SELECT provider_id, provider_name, type, endpoint, model_list,
                   description, created_at
            FROM llm_provider
            WHERE provider_id = ? AND is_deleted = 0
            LIMIT 1
            """,
            (payload["provider_id"],),
        )
        return {"success": True, "messages": rows}

    @data_store_handler
    async def update_llm_provider(self, payload: dict) -> dict:
        provider_type = payload.get("type")
        if isinstance(provider_type, str):
            provider_type = provider_type.lower()
        model_list = payload.get("model_list")
        if isinstance(model_list, list):
            model_list = json.dumps(model_list)
        await self._execute(
            """
            UPDATE llm_provider
            SET provider_name = COALESCE(?, provider_name),
                type = COALESCE(?, type),
                endpoint = COALESCE(?, endpoint),
                model_list = COALESCE(?, model_list),
                description = COALESCE(?, description),
                is_deleted = COALESCE(?, is_deleted)
            WHERE provider_id = ? AND user_uid = ? AND is_deleted = 0
            """,
            (
                payload.get("provider_name"),
                provider_type,
                payload.get("endpoint"),
                model_list,
                payload.get("description"),
                payload.get("is_deleted"),
                payload["provider_id"],
                payload["user_uid"],
            ),
        )
        return {"success": True, "messages": "success"}

    # --------------------------------------------------
    # MCP servers
    # --------------------------------------------------

    @data_store_handler
    async def create_mcp_server(self, payload: dict) -> dict:
        mcp_id = payload["mcp_id"]
        await self._execute(
            """
            INSERT INTO mcp_server (
                mcp_id, user_uid, mcp_name, transport, endpoint, config,
                description
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                mcp_id,
                payload["user_uid"],
                payload["mcp_name"],
                payload["transport"],
                payload["endpoint"],
                json.dumps(payload.get("config", {})),
                payload.get("description"),
            ),
        )
        return {"success": True, "messages": {"mcp_id": mcp_id}}

    @data_store_handler
    async def get_mcp_servers(self, payload: dict) -> dict:
        rows = await self._fetch_all(
            """
            SELECT mcp_id, mcp_name, transport, endpoint, config,
                   description, enabled, tool_count, created_at
            FROM mcp_server
            WHERE user_uid = ? AND is_deleted = 0
            ORDER BY created_at DESC
            """,
            (payload["user_uid"],),
        )
        return {"success": True, "messages": rows}

    @data_store_handler
    async def get_enabled_mcp_servers(self, payload: dict) -> dict:
        rows = await self._fetch_all(
            """
            SELECT mcp_id, mcp_name, transport, endpoint, config
            FROM mcp_server
            WHERE user_uid = ? AND enabled = 1 AND is_deleted = 0
            ORDER BY created_at ASC
            """,
            (payload["user_uid"],),
        )
        return {"success": True, "messages": rows}

    @data_store_handler
    async def update_mcp_server(self, payload: dict) -> dict:
        config = payload.get("config")
        if isinstance(config, (dict, list)):
            config = json.dumps(config)
        await self._execute(
            """
            UPDATE mcp_server
            SET mcp_name = COALESCE(?, mcp_name),
                transport = COALESCE(?, transport),
                endpoint = COALESCE(?, endpoint),
                config = COALESCE(?, config),
                description = COALESCE(?, description),
                enabled = COALESCE(?, enabled),
                tool_count = COALESCE(?, tool_count),
                is_deleted = COALESCE(?, is_deleted)
            WHERE mcp_id = ? AND user_uid = ? AND is_deleted = 0
            """,
            (
                payload.get("mcp_name"),
                payload.get("transport"),
                payload.get("endpoint"),
                config,
                payload.get("description"),
                payload.get("enabled"),
                payload.get("tool_count"),
                payload.get("is_deleted"),
                payload["mcp_id"],
                payload["user_uid"],
            ),
        )
        return {"success": True, "messages": "success"}

    # --------------------------------------------------
    # Cron tasks
    # --------------------------------------------------

    @data_store_handler
    async def create_cron_task(self, payload: dict) -> dict:
        task_id = payload["task_id"]
        await self._execute(
            """
            INSERT INTO cron_task (
                task_id, user_uid, conversation_uid, platform, name,
                prompt, execute, exec_time, repeat, extra_config, description
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                payload["user_uid"],
                payload.get("conversation_uid"),
                payload.get("platform") or "default",
                payload.get("task_name"),
                payload.get("prompt"),
                payload.get("execute"),
                payload.get("exec_time"),
                payload.get("repeat") or "once",
                self._json(payload.get("extra_config"), {}),
                payload.get("description", ""),
            ),
        )
        return {"success": True, "messages": {"task_id": task_id}}

    @data_store_handler
    async def get_all_enabled_cron_tasks(self, payload: dict) -> dict:
        rows = await self._fetch_all(
            """
            SELECT task_id, user_uid, conversation_uid, platform,
                   name, prompt, execute, exec_time, repeat, extra_config,
                   description, created_at, updated_at
            FROM cron_task
            WHERE enabled = 1 AND is_deleted = 0
            ORDER BY exec_time ASC
            """
        )
        return {"success": True, "messages": rows}

    @data_store_handler
    async def get_cron_tasks(self, payload: dict) -> dict:
        rows = await self._fetch_all(
            """
            SELECT task_id, conversation_uid, platform, name, prompt,
                   execute, exec_time, repeat, extra_config, description,
                   enabled, created_at, updated_at
            FROM cron_task
            WHERE user_uid = ? AND is_deleted = 0
            ORDER BY exec_time ASC
            """,
            (payload["user_uid"],),
        )
        return {"success": True, "messages": rows}

    @data_store_handler
    async def get_cron_task_by_id(self, payload: dict) -> dict:
        rows = await self._fetch_all(
            """
            SELECT task_id, user_uid, conversation_uid, platform, name,
                   prompt, execute, exec_time, repeat, extra_config,
                   description, enabled, created_at, updated_at
            FROM cron_task
            WHERE task_id = ? AND is_deleted = 0
            LIMIT 1
            """,
            (payload["task_id"],),
        )
        return {"success": True, "messages": rows}

    @data_store_handler
    async def update_cron_task(self, payload: dict) -> dict:
        extra_config = payload.get("extra_config")
        if isinstance(extra_config, (dict, list)):
            extra_config = json.dumps(extra_config)
        await self._execute(
            """
            UPDATE cron_task
            SET conversation_uid = COALESCE(?, conversation_uid),
                platform = COALESCE(?, platform),
                name = COALESCE(?, name),
                prompt = COALESCE(?, prompt),
                execute = COALESCE(?, execute),
                exec_time = COALESCE(?, exec_time),
                repeat = COALESCE(?, repeat),
                extra_config = COALESCE(?, extra_config),
                description = COALESCE(?, description),
                enabled = COALESCE(?, enabled),
                is_deleted = COALESCE(?, is_deleted),
                updated_at = CURRENT_TIMESTAMP
            WHERE task_id = ? AND is_deleted = 0
            """,
            (
                payload.get("conversation_uid"),
                payload.get("platform"),
                payload.get("task_name"),
                payload.get("prompt"),
                payload.get("execute"),
                payload.get("exec_time"),
                payload.get("repeat"),
                extra_config,
                payload.get("description"),
                payload.get("enabled"),
                payload.get("is_deleted"),
                payload["task_id"],
            ),
        )
        return {"success": True, "messages": "success"}


data_server = SqliteService()
auto_init.register(data_server)