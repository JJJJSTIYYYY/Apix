import json
import sqlite3

import pytest

from apix.agent.store.core.server.data_store.sqlite_server import SqliteService


@pytest.fixture
async def db(tmp_path):
    service = SqliteService(tmp_path / "nested" / "apix.sqlite3")
    await service.start()
    try:
        yield service
    finally:
        await service.stop()


async def create_user_and_conversation(
    db: SqliteService, monkeypatch, *, user_uid="user-1", conversation_uid="conv-1"
):
    created = await db.create_a_user(
        {"user_uid": user_uid, "username": f"name-{user_uid}", "password": "secret"}
    )
    assert created["success"] is True
    monkeypatch.setattr(db, "_conversation_id_generator", lambda: conversation_uid)
    conversation = await db.create_conversation(
        {
            "user_uid": user_uid,
            "platform": "web",
            "title": "Initial title",
            "workspace": "/workspace/demo",
        }
    )
    assert conversation == {"success": True, "messages": {"conversation_uid": conversation_uid}}


@pytest.mark.asyncio
async def test_lifecycle_helpers_and_transaction_rollback(tmp_path):
    path = tmp_path / "deep" / "database.sqlite3"
    service = SqliteService(path)

    with pytest.raises(RuntimeError, match="call start"):
        await service._fetch_all("SELECT 1")

    await service.start()
    connection = service._connection
    await service.start()
    assert service._connection is connection
    assert path.exists()
    tables = await service._fetch_all(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    )
    assert {row["name"] for row in tables} >= {
        "users",
        "conversations",
        "messages",
        "agent_skills",
        "rag_documents",
        "shortterm_memory",
        "longterm_memory",
        "llm_provider",
        "mcp_server",
        "cron_task",
    }
    message_columns = [
        row["name"]
        for row in await service._fetch_all("PRAGMA table_info(messages)")
    ]
    assert message_columns == [
        "id",
        "message_uid",
        "msg_cursor",
        "user_uid",
        "conversation_id",
        "conversation_uid",
        "generation_id",
        "node_id",
        "parent_id",
        "role",
        "name",
        "content",
        "metadata",
        "extensions",
        "timestamp",
        "is_deleted",
    ]

    def fail_after_insert(conn):
        conn.execute(
            "INSERT INTO users (user_uid, username, password) VALUES (?, ?, ?)",
            ("rolled-back", "rolled-back", "secret"),
        )
        raise RuntimeError("force rollback")

    with pytest.raises(RuntimeError, match="force rollback"):
        await service._run(fail_after_insert)
    assert await service._fetch_all(
        "SELECT * FROM users WHERE user_uid = ?", ("rolled-back",)
    ) == []
    assert service._json(None, {}) == "{}"
    assert service._json(["a"], []) == '["a"]'
    assert service._json('{"already":"json"}', {}) == '{"already":"json"}'
    assert service._normalize_row(
        {
            "created_at": "2026-01-02 03:04:05",
            "timestamp": "2026-01-02 03:04:06",
            "content": "leave me alone",
        }
    ) == {
        "created_at": "2026-01-02T03:04:05",
        "timestamp": "2026-01-02T03:04:06",
        "content": "leave me alone",
    }

    await service.stop()
    await service.stop()
    with pytest.raises(RuntimeError, match="call start"):
        await service._execute("SELECT 1")


@pytest.mark.asyncio
async def test_users_conversations_and_messages(db, monkeypatch):
    assert await db.ensure_user_exists(
        {"user_uid": "user-1", "username": "alice"}
    ) == {"success": False, "messages": "fail: User do not exist."}
    assert (await db.create_a_user(
        {"user_uid": "user-1", "username": "alice", "password": "secret"}
    ))["success"]
    assert await db.verify_user({"username": "alice", "password": "secret"}) == {
        "success": True,
        "messages": {"msg": "success", "uid": "user-1"},
    }
    assert (await db.verify_user({"username": "alice", "password": "wrong"}))[
        "success"
    ] is False
    assert (await db.ensure_user_exists(
        {"user_uid": "user-1", "username": "alice"}
    ))["success"]
    assert (await db.ensure_user_exists(
        {"user_uid": "new", "username": "alice"}, exist=False
    ))["success"] is False
    assert (await db.create_a_user(
        {"user_uid": "duplicate", "username": "alice", "password": "secret"}
    ))["success"] is False

    monkeypatch.setattr(db, "_conversation_id_generator", lambda: "conv-1")
    assert await db.create_conversation(
        {
            "user_uid": "user-1",
            "title": None,
            "workspace": "/tmp/work",
            "is_cron": True,
        }
    ) == {"success": True, "messages": {"conversation_uid": "conv-1"}}
    conversations = (await db.fetch_conversation_list({"user_uid": "user-1"}))[
        "messages"
    ]
    assert conversations[0]["title"] == "New Conversation..."
    assert conversations[0]["work_space"] == "/tmp/work"
    assert conversations[0]["is_cron"] == 1
    assert "T" in conversations[0]["created_at"]

    assert await db.update_conversation(
        {
            "user_uid": "user-1",
            "conversation_uid": "conv-1",
            "title": "Renamed",
            "workspace": "/tmp/new",
            "is_pinned": True,
        }
    ) == {"success": True, "messages": "success"}
    meta = (await db.get_conversation_meta_by_id(
        {"conversation_uid": "conv-1"}
    ))["messages"][0]
    assert (meta["title"], meta["work_space"], meta["is_pinned"]) == (
        "Renamed",
        "/tmp/new",
        1,
    )

    first = await db.append_message(
        {
            "user_uid": "user-1",
            "conversation_uid": "conv-1",
            "message": {
                "message_uid": "message-1",
                "role": "user",
                "name": "alice",
                "content": "hello sqlite",
                "node_id": "node-1",
                "metadata": None,
                "extensions": {"uploaded_files": ["brief.pdf"]},
            },
        }
    )
    second = await db.append_message(
        {
            "user_uid": "user-1",
            "conversation_uid": "conv-1",
            "message": {
                "message_uid": "message-2",
                "role": "ai",
                "name": "assistant",
                "content": "hello back",
                "generation_id": "gen-1",
                "node_id": "node-2",
                "parent_id": "node-1",
                "metadata": {"model": "demo-model"},
                "extensions": {"reasoning": "because"},
            },
        }
    )
    assert first["messages"]["msg_cursor"] == 1
    assert second["messages"]["msg_cursor"] == 2
    assert "T" in first["messages"]["timestamp"]
    conversation_row = (
        await db._fetch_all(
            "SELECT latest_cursor, has_new_message FROM conversations"
        )
    )[0]
    assert conversation_row == {
        "latest_cursor": 2,
        "has_new_message": 1,
    }

    fetched = await db.fetch_messages_after_cursor(
        {
            "user_uid": "user-1",
            "conversation_uid": "conv-1",
            "cursor": -5,
            "limit": 1,
        }
    )
    assert [row["msg_cursor"] for row in fetched["messages"]] == [1]
    assert fetched["next_cursor"] == 2
    assert fetched["messages"][0]["message_uid"] == "message-1"
    assert fetched["messages"][0]["name"] == "alice"
    assert json.loads(fetched["messages"][0]["metadata"]) == {}
    assert json.loads(fetched["messages"][0]["extensions"]) == {
        "uploaded_files": ["brief.pdf"]
    }
    assert (await db.fetch_messages_after_cursor(
        {"user_uid": "user-1", "conversation_uid": "conv-1", "cursor": 99}
    ))["next_cursor"] == 99

    matches = await db.search_messages_by_keyword(
        {"user_uid": "user-1", "keyword": "hello_sqlite"}
    )
    assert [row["content"] for row in matches["messages"]] == ["hello sqlite"]
    assert await db.search_messages_by_keyword(
        {"user_uid": "user-1", "keyword": "% _ \\"}
    ) == {"success": True, "messages": []}

    deleted = await db.delete_messages(
        {
            "user_uid": "user-1",
            "conversation_uid": "conv-1",
            "messages": ["node-1", "missing"],
        }
    )
    assert deleted == {
        "success": True,
        "messages": [{"message_uid": "message-1"}],
    }
    assert (await db.search_messages_by_keyword(
        {"user_uid": "user-1", "keyword": "sqlite"}
    ))["messages"] == []

    for result in (
        await db.append_message(
            {"user_uid": "user-1", "conversation_uid": "conv-1", "message": {}}
        ),
        await db.delete_messages(
            {"user_uid": "user-1", "conversation_uid": "conv-1", "messages": []}
        ),
    ):
        assert result["success"] is False


@pytest.mark.asyncio
async def test_skills_and_shortterm_memory(db, monkeypatch):
    await create_user_and_conversation(db, monkeypatch)

    skills = [
        {
            "skill_id": "skill-1",
            "skill_name": "Search",
            "skill_description": "Search things",
            "skill_version": "2.0",
            "package_path": "/skills/search.zip",
            "package_size": 123,
            "package_sha256": "abc",
        },
        {
            "skill_id": "skill-2",
            "skill_name": "Write",
            "skill_description": "Write things",
            "package_path": "/skills/write.zip",
            "package_size": 456,
        },
    ]
    assert (await db.insert_skill_info(
        {"user_uid": "user-1", "skills": skills}
    ))["success"]
    assert len((await db.fetch_available_skills(
        {"user_uid": "user-1", "limit": 1}
    ))["messages"]) == 1
    target = (await db.fetch_target_skill(
        {"user_uid": "user-1", "skill_id": "skill-1"}
    ))["messages"][0]
    assert target["skill_version"] == "2.0"
    assert await db.update_skill_status(
        {
            "user_uid": "user-1",
            "skill_id": "skill-1",
            "is_active": True,
        }
    ) == {"success": True, "messages": "success"}
    assert (await db.fetch_target_skill(
        {"user_uid": "user-1", "skill_id": "skill-1"}
    ))["messages"][0]["is_active"] == 1
    await db.update_skill_status(
        {"user_uid": "user-1", "skill_id": "skill-1", "deleted": True}
    )
    assert (await db.fetch_target_skill(
        {"user_uid": "user-1", "skill_id": "skill-1"}
    ))["messages"] == []

    assert await db.insert_shortterm_memory(
        {
            "memory_id": "memory-1",
            "user_uid": "user-1",
            "conversation_uid": "conv-1",
            "content": "remember this",
        }
    ) == {"success": True, "messages": "success"}
    memory = (await db.fetch_shortterm_memory(
        {"user_uid": "user-1", "conversation_uid": "conv-1"}
    ))["messages"][0]
    assert memory["memory_id"] == "memory-1"
    await db.delete_shortterm_memory(
        {
            "memory_ids": ["memory-1"],
            "user_uid": "user-1",
            "conversation_uid": "conv-1",
        }
    )
    assert (await db.fetch_shortterm_memory(
        {"user_uid": "user-1", "conversation_uid": "conv-1"}
    ))["messages"] == []
    assert (await db.delete_shortterm_memory(
        {"memory_ids": [], "user_uid": "user-1", "conversation_uid": "conv-1"}
    ))["success"]


@pytest.mark.asyncio
async def test_longterm_memory_crud_and_constraints(db):
    assert (await db.create_a_user(
        {
            "user_uid": "user-1",
            "username": "alice",
            "password": "secret",
        }
    ))["success"]

    assert await db.insert_longterm_memory(
        {
            "memory_id": "memory-1",
            "user_uid": "user-1",
            "title": "First memory",
            "date": "2025-06-07",
            "content": "Remember this",
            "source": "conversation",
        }
    ) == {
        "success": True,
        "messages": {"memory_id": "memory-1"},
    }
    assert (await db.insert_longterm_memory(
        {
            "memory_id": "memory-2",
            "user_uid": "user-1",
            "title": "Second memory",
            "date": "2026-07-30",
            "content": "Workspace preference",
            "source": "workspace",
        }
    ))["success"]

    fetched = await db.fetch_longterm_memory({"user_uid": "user-1"})
    assert fetched == {
        "success": True,
        "messages": [
            {
                "memory_id": "memory-2",
                "title": "Second memory",
                "date": "2026-07-30",
                "content": "Workspace preference",
                "source": "workspace",
            },
            {
                "memory_id": "memory-1",
                "title": "First memory",
                "date": "2025-06-07",
                "content": "Remember this",
                "source": "conversation",
            },
        ],
    }

    assert await db.update_longterm_memory(
        {
            "memory_id": "memory-1",
            "user_uid": "user-1",
            "title": "Updated memory",
            "date": "2027-01-02",
            "content": "Updated content",
            "source": "workspace",
        }
    ) == {"success": True, "messages": "success"}
    updated = (await db.fetch_longterm_memory(
        {"user_uid": "user-1"}
    ))["messages"][0]
    assert updated == {
        "memory_id": "memory-1",
        "title": "Updated memory",
        "date": "2027-01-02",
        "content": "Updated content",
        "source": "workspace",
    }

    assert await db.update_longterm_memory(
        {
            "memory_id": "memory-1",
            "user_uid": "user-1",
            "is_deleted": True,
        }
    ) == {"success": True, "messages": "success"}
    assert (await db.fetch_longterm_memory(
        {"user_uid": "user-1"}
    ))["messages"] == [
        {
            "memory_id": "memory-2",
            "title": "Second memory",
            "date": "2026-07-30",
            "content": "Workspace preference",
            "source": "workspace",
        }
    ]
    deleted_row = (await db._fetch_all(
        """
        SELECT is_deleted, deleted_at
        FROM longterm_memory
        WHERE memory_id = ?
        """,
        ("memory-1",),
    ))[0]
    assert deleted_row["is_deleted"] == 1
    assert "T" in deleted_row["deleted_at"]

    assert not (await db.insert_longterm_memory(
        {
            "memory_id": "invalid-source",
            "user_uid": "user-1",
            "title": "Invalid",
            "date": "2025-06-07",
            "content": "Invalid",
            "source": "external",
        }
    ))["success"]
    assert not (await db.insert_longterm_memory(
        {
            "memory_id": "invalid-date",
            "user_uid": "user-1",
            "title": "Invalid",
            "date": "not-a-date",
            "content": "Invalid",
            "source": "conversation",
        }
    ))["success"]


@pytest.mark.asyncio
async def test_provider_mcp_and_cron_crud(db, monkeypatch):
    await create_user_and_conversation(db, monkeypatch)

    assert await db.create_llm_provider(
        {
            "provider_id": "provider-1",
            "user_uid": "user-1",
            "provider_name": "Primary",
            "type": "OPENAI",
            "endpoint": "https://example.test/v1",
            "model_list": ["model-a"],
            "description": "initial",
        }
    ) == {"success": True, "messages": {"provider_id": "provider-1"}}
    provider = (await db.get_llm_provider_by_id(
        {"provider_id": "provider-1"}
    ))["messages"][0]
    assert provider["type"] == "openai"
    assert json.loads(provider["model_list"]) == ["model-a"]
    assert len((await db.get_llm_providers({"user_uid": "user-1"}))["messages"]) == 1
    assert await db.update_llm_provider(
        {
            "provider_id": "provider-1",
            "user_uid": "user-1",
            "provider_name": "Updated",
            "type": "ANTHROPIC",
            "model_list": ["claude"],
        }
    ) == {"success": True, "messages": "success"}
    provider = (await db.get_llm_provider_by_id(
        {"provider_id": "provider-1"}
    ))["messages"][0]
    assert provider["provider_name"] == "Updated"
    assert provider["type"] == "anthropic"
    assert (await db.create_llm_provider(
        {
            "provider_id": "provider-1",
            "user_uid": "user-1",
            "provider_name": "duplicate",
            "endpoint": "x",
            "model_list": [],
        }
    ))["success"] is False

    assert await db.create_mcp_server(
        {
            "mcp_id": "mcp-1",
            "user_uid": "user-1",
            "mcp_name": "Tools",
            "transport": "stdio",
            "endpoint": None,
            "config": {"command": "demo"},
            "description": "tool server",
        }
    ) == {"success": True, "messages": {"mcp_id": "mcp-1"}}
    mcp = (await db.get_mcp_servers({"user_uid": "user-1"}))["messages"][0]
    assert json.loads(mcp["config"]) == {"command": "demo"}
    assert len((await db.get_enabled_mcp_servers(
        {"user_uid": "user-1"}
    ))["messages"]) == 1
    await db.update_mcp_server(
        {
            "mcp_id": "mcp-1",
            "user_uid": "user-1",
            "mcp_name": "Updated tools",
            "config": {"command": "new"},
            "enabled": False,
            "tool_count": 7,
        }
    )
    assert (await db.get_enabled_mcp_servers(
        {"user_uid": "user-1"}
    ))["messages"] == []
    mcp = (await db.get_mcp_servers({"user_uid": "user-1"}))["messages"][0]
    assert (mcp["mcp_name"], mcp["tool_count"]) == ("Updated tools", 7)

    assert await db.create_cron_task(
        {
            "task_id": "task-1",
            "user_uid": "user-1",
            "conversation_uid": "conv-1",
            "task_name": "Daily check",
            "prompt": "check",
            "execute": "run()",
            "exec_time": "2026-07-22 09:30:00",
            "repeat": "day",
            "extra_config": {"timezone": "Asia/Tokyo"},
        }
    ) == {"success": True, "messages": {"task_id": "task-1"}}
    task = (await db.get_cron_task_by_id({"task_id": "task-1"}))[
        "messages"
    ][0]
    assert task["platform"] == "default"
    assert task["exec_time"] == "2026-07-22T09:30:00"
    assert json.loads(task["extra_config"]) == {"timezone": "Asia/Tokyo"}
    assert len((await db.get_cron_tasks({"user_uid": "user-1"}))["messages"]) == 1
    assert len((await db.get_all_enabled_cron_tasks({}))["messages"]) == 1
    assert await db.update_cron_task(
        {
            "task_id": "task-1",
            "task_name": "Weekly check",
            "repeat": "week",
            "extra_config": {"weekday": 1},
            "enabled": False,
        }
    ) == {"success": True, "messages": "success"}
    task = (await db.get_cron_task_by_id({"task_id": "task-1"}))[
        "messages"
    ][0]
    assert (task["name"], task["repeat"], task["enabled"]) == (
        "Weekly check",
        "week",
        0,
    )
    assert (await db.get_all_enabled_cron_tasks({}))["messages"] == []
    await db.update_cron_task({"task_id": "task-1", "is_deleted": True})
    assert (await db.get_cron_task_by_id({"task_id": "task-1"}))[
        "messages"
    ] == []

    await db.update_llm_provider(
        {"provider_id": "provider-1", "user_uid": "user-1", "is_deleted": True}
    )
    await db.update_mcp_server(
        {"mcp_id": "mcp-1", "user_uid": "user-1", "is_deleted": True}
    )
    assert (await db.get_llm_providers({"user_uid": "user-1"}))["messages"] == []
    assert (await db.get_mcp_servers({"user_uid": "user-1"}))["messages"] == []
