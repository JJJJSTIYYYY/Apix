import json
from unittest.mock import AsyncMock

import pytest

from apix.agent.store.core.server.data_store import mysql_server as mysql_module
from apix.agent.store.core.server.data_store.mysql_server import MysqlService


def make_service():
    return MysqlService(
        host="localhost",
        port=3306,
        user="user",
        password="password",
        database="database",
    )


class AsyncContext:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class FakeCursor:
    def __init__(self, result_sets):
        self.result_sets = result_sets
        self.index = 0
        self.executions = []

    async def execute(self, sql, params=None):
        self.executions.append((sql, params))

    async def fetchall(self):
        return self.result_sets[self.index]

    async def nextset(self):
        self.index += 1
        return self.index < len(self.result_sets)


class FakeConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return AsyncContext(self._cursor)


class FakePool:
    def __init__(self, cursor=None):
        self.cursor = cursor
        self.closed = False
        self.waited = False

    def acquire(self):
        return AsyncContext(FakeConnection(self.cursor))

    def close(self):
        self.closed = True

    async def wait_closed(self):
        self.waited = True


@pytest.mark.asyncio
async def test_start_and_stop_are_idempotent(monkeypatch):
    service = make_service()
    pool = FakePool()
    create_pool = AsyncMock(return_value=pool)
    monkeypatch.setattr(mysql_module.aiomysql, "create_pool", create_pool)

    await service.start()
    await service.start()
    create_pool.assert_awaited_once_with(**service._pool_args)
    assert service._pool is pool

    await service.stop()
    await service.stop()
    assert pool.closed is True
    assert pool.waited is True
    assert service._pool is None


@pytest.mark.asyncio
async def test_call_procedure_executes_and_consumes_all_result_sets():
    cursor = FakeCursor(
        [
            [{"ignored": 1}],
            [{"value": "business result"}],
            [{"affected_rows": 1}],
        ]
    )
    service = make_service()
    service._pool = FakePool(cursor)

    result = await service._call_procedure("demo", ("a", 2))

    assert cursor.executions == [("CALL demo(%s, %s)", ("a", 2))]
    assert result == [{"value": "business result"}]
    assert cursor.index == 3


@pytest.mark.asyncio
async def test_call_procedure_without_parameters_and_without_pool():
    service = make_service()
    with pytest.raises(RuntimeError, match="not initialized"):
        await service._call_procedure("demo")

    cursor = FakeCursor([[{"value": 1}]])
    service._pool = FakePool(cursor)
    assert await service._call_procedure("demo", ()) == [{"value": 1}]
    assert cursor.executions == [("CALL demo()", None)]


@pytest.mark.asyncio
async def test_user_conversation_and_message_wrappers(monkeypatch):
    service = make_service()
    call = AsyncMock(return_value=[])
    monkeypatch.setattr(service, "_call_procedure", call)

    assert await service.create_a_user(
        {"user_uid": "u-1", "username": "alice", "password": "secret"}
    ) == {"success": True, "messages": {"msg": "success", "uid": "u-1"}}
    call.assert_awaited_with("create_user", ("u-1", "alice", "secret"))

    call.return_value = [{"user_uid": "u-1"}]
    assert (await service.verify_user(
        {"username": "alice", "password": "secret"}
    ))["messages"]["uid"] == "u-1"
    call.return_value = []
    assert (await service.verify_user(
        {"username": "alice", "password": "bad"}
    ))["success"] is False
    assert (await service.ensure_user_exists(
        {"user_uid": "u-1", "username": "alice"}
    ))["success"] is False
    call.return_value = [{"user_uid": "u-1"}]
    assert (await service.ensure_user_exists(
        {"user_uid": "u-1"}, exist=True
    ))["success"]
    assert (await service.ensure_user_exists(
        {"user_uid": "u-1"}, exist=False
    ))["success"] is False

    call.return_value = []
    monkeypatch.setattr(service, "_conversation_id_generator", lambda: "conv-1")
    assert await service.create_conversation(
        {
            "user_uid": "u-1",
            "platform": "web",
            "title": "Title",
            "workspace": "/work",
            "is_cron": True,
        }
    ) == {"success": True, "messages": "conv-1"}
    call.assert_awaited_with(
        "create_conversation", ("u-1", "web", "conv-1", "Title", "/work", True)
    )
    assert await service.update_conversation(
        {
            "user_uid": "u-1",
            "conversation_uid": "conv-1",
            "title": "New",
            "workspace": "/new",
            "is_pinned": True,
            "is_deleted": False,
            "has_new_message": True,
        }
    ) == {"success": True, "messages": "conv-1"}
    call.assert_awaited_with(
        "update_conversation",
        ("u-1", "conv-1", "New", "/new", True, False, True),
    )

    call.return_value = [{"msg_cursor": 3, "created_at": "now"}]
    message = {
        "role": "ai",
        "content": "answer",
        "think": "thought",
        "extra": {"x": "你好"},
        "info": None,
        "generation_id": "g-1",
        "node_id": "n-1",
        "parent_id": "root",
    }
    result = await service.append_message(
        {"user_uid": "u-1", "conversation_uid": "conv-1", "message": message}
    )
    assert result == {
        "success": True,
        "messages": {"msg_cursor": 3, "created_at": "now"},
    }
    params = call.await_args.args[1]
    assert call.await_args.args[0] == "append_message"
    assert json.loads(params[5]) == {"x": "你好"}
    assert json.loads(params[6]) == {}
    assert params[7:] == ("g-1", "n-1", "root")
    assert (await service.append_message(
        {"user_uid": "u-1", "conversation_uid": "conv-1", "message": {}}
    ))["success"] is False
    call.return_value = [{"msg_cursor": -1}]
    assert (await service.append_message(
        {
            "user_uid": "u-1",
            "conversation_uid": "conv-1",
            "message": {"role": "user", "content": "x"},
        }
    ))["success"] is False


@pytest.mark.asyncio
async def test_message_delete_fetch_and_search(monkeypatch):
    service = make_service()
    call = AsyncMock()
    monkeypatch.setattr(service, "_call_procedure", call)
    call.side_effect = [
        [{"info": '{"id":"one"}'}, {"info": "invalid"}, "ignored"],
        [{"info": {"id": "two"}}, {"info": None}],
    ]
    deleted = await service.delete_messages(
        {
            "user_uid": "u-1",
            "conversation_uid": "c-1",
            "messages": ["node-1", "node-2"],
        }
    )
    assert deleted == {
        "success": True,
        "messages": [{"id": "one"}, {"id": "two"}],
    }
    assert call.await_args_list[0].args == (
        "delete_messages_node",
        ("u-1", "c-1", "node-1"),
    )
    assert (await service.delete_messages(
        {"user_uid": "u-1", "conversation_uid": "c-1", "messages": []}
    ))["success"] is False

    call.side_effect = None
    call.return_value = [{"msg_cursor": 5}, {"msg_cursor": 6}]
    fetched = await service.fetch_messages_after_cursor(
        {"user_uid": "u-1", "conversation_uid": "c-1", "cursor": -3, "limit": 2}
    )
    assert fetched["next_cursor"] == 7
    call.assert_awaited_with("fetch_messages_after_cursor", ("u-1", "c-1", 0, 2))
    call.return_value = []
    assert (await service.fetch_messages_after_cursor(
        {"user_uid": "u-1", "conversation_uid": "c-1", "cursor": 8}
    ))["next_cursor"] == 8

    call.return_value = [{"content": "match"}]
    searched = await service.search_messages_by_keyword(
        {"user_uid": "u-1", "keyword": "  foo__bar\\baz  "}
    )
    assert searched["messages"] == [{"content": "match"}]
    call.assert_awaited_with("search_messages_by_keyword", ("u-1", "foo%bar%baz"))
    call.reset_mock()
    assert await service.search_messages_by_keyword(
        {"user_uid": "u-1", "keyword": " % _ \\ "}
    ) == {"success": True, "messages": []}
    call.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,payload,procedure,params",
    [
        ("fetch_conversation_list", {"user_uid": 7}, "fetch_conversation_list", ("7",)),
        (
            "get_conversation_meta_by_id",
            {"conversation_uid": "c-1"},
            "get_conversation_meta_by_id",
            ("c-1",),
        ),
        (
            "fetch_available_skills",
            {"user_uid": "u-1", "limit": 3},
            "fetch_agent_skills",
            ("u-1", 3),
        ),
        (
            "fetch_target_skill",
            {"user_uid": "u-1", "skill_id": "s-1"},
            "fetch_target_skill",
            ("u-1", "s-1"),
        ),
        (
            "fetch_available_documents",
            {"user_uid": "u-1", "limit": 4},
            "fetch_rag_documents",
            ("u-1", 4),
        ),
        (
            "fetch_target_document",
            {"user_uid": "u-1", "document_id": "d-1"},
            "fetch_target_document",
            ("u-1", "d-1"),
        ),
        (
            "fetch_shortterm_memory",
            {"user_uid": "u-1", "conversation_uid": "c-1"},
            "fetch_shortterm_memory",
            ("u-1", "c-1"),
        ),
        ("get_llm_providers", {"user_uid": "u-1"}, "get_llm_providers", ("u-1",)),
        (
            "get_llm_provider_by_id",
            {"provider_id": "p-1"},
            "get_llm_provider_by_id",
            ("p-1",),
        ),
        ("get_mcp_servers", {"user_uid": "u-1"}, "get_mcp_servers", ("u-1",)),
        (
            "get_enabled_mcp_servers",
            {"user_uid": "u-1"},
            "get_enabled_mcp_servers",
            ("u-1",),
        ),
        (
            "get_all_enabled_cron_tasks",
            {},
            "get_all_enabled_cron_tasks",
            (),
        ),
        ("get_cron_tasks", {"user_uid": "u-1"}, "get_cron_tasks", ("u-1",)),
        (
            "get_cron_task_by_id",
            {"task_id": "t-1"},
            "get_cron_task_by_id",
            ("t-1",),
        ),
    ],
)
async def test_read_wrappers_forward_parameters(
    monkeypatch, method, payload, procedure, params
):
    service = make_service()
    rows = [{"result": method}]
    call = AsyncMock(return_value=rows)
    monkeypatch.setattr(service, "_call_procedure", call)

    result = await getattr(service, method)(payload)

    assert result == {"success": True, "messages": rows}
    call.assert_awaited_once_with(procedure, params)


@pytest.mark.asyncio
async def test_skill_and_document_mutations(monkeypatch):
    service = make_service()
    call = AsyncMock(return_value=[])
    monkeypatch.setattr(service, "_call_procedure", call)
    skills = [
        {
            "skill_id": "s-1",
            "skill_name": "One",
            "skill_description": "First",
            "skill_version": "2.0",
            "package_path": "/one.zip",
            "package_size": 10,
            "package_sha256": "hash-1",
        },
        {
            "skill_id": "s-2",
            "skill_name": "Two",
            "skill_description": "Second",
            "package_path": "/two.zip",
            "package_size": 20,
        },
    ]
    assert (await service.insert_skill_info(
        {"user_uid": "u-1", "skills": skills}
    ))["success"]
    assert call.await_args_list[0].args == (
        "insert_agent_skill",
        ("s-1", "One", "First", "2.0", "/one.zip", 10, "hash-1", "u-1"),
    )
    assert call.await_args_list[1].args[1][3] == "v1.0"
    await service.update_skill_status(
        {"user_uid": "u-1", "skill_id": "s-1", "is_active": True, "deleted": False}
    )
    call.assert_awaited_with("update_agent_skill", ("s-1", "u-1", True, False))

    document = {
        "file_id": "d-1",
        "file_name": "doc.pdf",
        "file_type": "application/pdf",
        "file_path": "/doc.pdf",
        "file_size": 99,
        "sha256": "doc-hash",
    }
    await service.insert_rag_document(
        {"user_uid": "u-1", "file_info": [document]}
    )
    call.assert_awaited_with(
        "insert_rag_document",
        ("d-1", "doc.pdf", "", "application/pdf", "/doc.pdf", 99, "doc-hash", "u-1"),
    )
    await service.update_document_status(
        {
            "user_uid": "u-1",
            "document_id": "d-1",
            "description": "ready",
            "embed_engine": ["embedding"],
            "is_active": True,
            "deleted": False,
        }
    )
    call.assert_awaited_with(
        "update_rag_document",
        ("d-1", "u-1", True, False, "ready", '["embedding"]'),
    )


@pytest.mark.asyncio
async def test_memory_provider_mcp_and_cron_mutations(monkeypatch):
    service = make_service()
    call = AsyncMock(return_value=[])
    monkeypatch.setattr(service, "_call_procedure", call)
    monkeypatch.setattr(mysql_module.time, "time", lambda: 12.345678)

    await service.insert_shortterm_memory(
        {
            "memory_id": "m-1",
            "user_uid": "u-1",
            "conversation_uid": "c-1",
            "content": "remember",
        }
    )
    call.assert_awaited_with(
        "insert_shortterm_memory", ("m-1", "u-1", "c-1", "remember", 12345678)
    )
    await service.delete_shortterm_memory(
        {"memory_ids": ["m-1"], "user_uid": "u-1", "conversation_uid": "c-1"}
    )
    call.assert_awaited_with(
        "delete_shortterm_memory", ('["m-1"]', "u-1", "c-1")
    )

    provider_payload = {
        "provider_id": "p-1",
        "user_uid": "u-1",
        "provider_name": "Provider",
        "type": "OPENAI",
        "endpoint": "https://example.test",
        "model_list": ["model"],
        "description": "desc",
    }
    assert (await service.create_llm_provider(provider_payload))["messages"] == {
        "provider_id": "p-1"
    }
    call.assert_awaited_with(
        "create_llm_provider",
        ("p-1", "u-1", "Provider", "openai", "https://example.test", '["model"]', "desc"),
    )
    await service.update_llm_provider(
        {
            "provider_id": "p-1",
            "user_uid": "u-1",
            "type": "ANTHROPIC",
            "model_list": ["claude"],
            "is_deleted": False,
        }
    )
    call.assert_awaited_with(
        "update_llm_provider",
        ("p-1", "u-1", None, "anthropic", None, '["claude"]', None, False),
    )

    await service.create_mcp_server(
        {
            "mcp_id": "server-1",
            "user_uid": "u-1",
            "mcp_name": "Tools",
            "transport": "stdio",
            "endpoint": None,
            "config": {"command": "run"},
        }
    )
    call.assert_awaited_with(
        "create_mcp_server",
        ("server-1", "u-1", "Tools", "stdio", None, '{"command": "run"}', None),
    )
    await service.update_mcp_server(
        {
            "mcp_id": "server-1",
            "user_uid": "u-1",
            "config": ["new"],
            "enabled": True,
            "tool_count": 2,
            "is_deleted": False,
        }
    )
    call.assert_awaited_with(
        "update_mcp_server",
        ("server-1", "u-1", None, None, None, '["new"]', None, True, 2, False),
    )

    cron = {
        "task_id": "task-1",
        "user_uid": "u-1",
        "conversation_uid": "c-1",
        "platform": "web",
        "task_name": "Task",
        "prompt": "prompt",
        "execute": "run()",
        "exec_time": "2026-01-01T00:00:00",
        "repeat": "day",
        "extra_config": None,
        "description": "desc",
    }
    await service.create_cron_task(cron)
    call.assert_awaited_with(
        "create_cron_task",
        (
            "task-1", "u-1", "c-1", "web", "Task", "prompt", "run()",
            "2026-01-01T00:00:00", "day", "{}", "desc",
        ),
    )
    await service.update_cron_task(
        {"task_id": "task-1", "extra_config": {"x": 1}, "enabled": False}
    )
    call.assert_awaited_with(
        "update_cron_task",
        ("task-1", None, None, None, None, None, None, None, '{"x": 1}', None, False, None),
    )


@pytest.mark.asyncio
async def test_public_wrapper_converts_database_error(monkeypatch):
    service = make_service()
    monkeypatch.setattr(
        service, "_call_procedure", AsyncMock(side_effect=RuntimeError("database down"))
    )

    result = await service.get_mcp_servers({"user_uid": "u-1"})

    assert result == {"success": False, "messages": "fail: database down"}
