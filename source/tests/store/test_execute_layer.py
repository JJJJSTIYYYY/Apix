"""Comprehensive tests for the store execution-layer orchestration."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from apix.agent.store.core import execute_layer as execute_module
from apix.agent.store.core.execute_layer import DataExecutors


def _executor(
    *,
    data_store=None,
    cache_store=None,
    file_server=None,
    rag_server=None,
) -> DataExecutors:
    return DataExecutors(
        data_store=data_store or SimpleNamespace(),
        cache_store=cache_store or SimpleNamespace(),
        file_server=file_server or SimpleNamespace(),
        rag_server=rag_server or SimpleNamespace(),
    )


def _row(
    node_id: str,
    parent_id: str,
    cursor: int,
    role: str,
    *,
    deleted: bool = False,
    extra=None,
    info=None,
) -> dict:
    return {
        "node_id": node_id,
        "parent_id": parent_id,
        "msg_cursor": cursor,
        "role": role,
        "is_deleted": deleted,
        "extra": {} if extra is None else extra,
        "info": {} if info is None else info,
        "content": f"{node_id}:{cursor}",
    }


def test_export_handlers_returns_only_decorated_async_methods():
    executor = _executor()
    executor.public_value = 1
    executor.public_callable = lambda: None

    handlers = executor.export_handlers()

    assert handlers["append_message"] == executor.append_message
    assert handlers["get_messages"] == executor.get_messages
    assert handlers["create_cron_task"] == executor.create_cron_task
    assert "export_handlers" not in handlers
    assert "public_callable" not in handlers
    assert "public_value" not in handlers


def test_export_handlers_rejects_decorated_sync_method(monkeypatch):
    def invalid_handler(self, payload):
        return payload

    invalid_handler._handler_name = "invalid_handler"
    monkeypatch.setattr(
        DataExecutors,
        "invalid_handler",
        invalid_handler,
        raising=False,
    )

    with pytest.raises(TypeError, match="must be async"):
        _executor().export_handlers()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("executor_method", "service_name", "store_method"),
    [
        ("verify_user", "data_store", "verify_user"),
        ("ensure_user_exists", "data_store", "ensure_user_exists"),
        (
            "fetch_conversation_list",
            "data_store",
            "fetch_conversation_list",
        ),
        (
            "get_conversation_meta_by_id",
            "data_store",
            "get_conversation_meta_by_id",
        ),
        (
            "search_messages_by_keyword",
            "data_store",
            "search_messages_by_keyword",
        ),
        (
            "get_current_messages_branch_chain",
            "cache_store",
            "get_current_messages_branch_chain",
        ),
        (
            "fetch_shortterm_memory",
            "data_store",
            "fetch_shortterm_memory",
        ),
        (
            "insert_shortterm_memory",
            "data_store",
            "insert_shortterm_memory",
        ),
        ("update_llm_provider", "data_store", "update_llm_provider"),
        ("update_mcp_server", "data_store", "update_mcp_server"),
        ("update_cron_task", "data_store", "update_cron_task"),
    ],
)
async def test_simple_handlers_forward_payload(
    executor_method,
    service_name,
    store_method,
):
    payload = {"value": 1}
    expected = {"success": True, "messages": "ok"}
    handler = AsyncMock(return_value=expected)
    service = SimpleNamespace(**{store_method: handler})
    executor = _executor(**{service_name: service})

    assert await getattr(executor, executor_method)(payload) == expected
    handler.assert_awaited_once_with(payload)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("executor_method", "service_name", "store_method"),
    [
        ("verify_user", "data_store", "verify_user"),
        ("ensure_user_exists", "data_store", "ensure_user_exists"),
        (
            "fetch_conversation_list",
            "data_store",
            "fetch_conversation_list",
        ),
        (
            "get_conversation_meta_by_id",
            "data_store",
            "get_conversation_meta_by_id",
        ),
        (
            "search_messages_by_keyword",
            "data_store",
            "search_messages_by_keyword",
        ),
        (
            "get_current_messages_branch_chain",
            "cache_store",
            "get_current_messages_branch_chain",
        ),
        (
            "fetch_shortterm_memory",
            "data_store",
            "fetch_shortterm_memory",
        ),
        (
            "insert_shortterm_memory",
            "data_store",
            "insert_shortterm_memory",
        ),
        ("update_llm_provider", "data_store", "update_llm_provider"),
        ("update_mcp_server", "data_store", "update_mcp_server"),
        ("update_cron_task", "data_store", "update_cron_task"),
    ],
)
async def test_simple_handlers_normalize_exceptions(
    executor_method,
    service_name,
    store_method,
):
    handler = AsyncMock(side_effect=RuntimeError("service down"))
    service = SimpleNamespace(**{store_method: handler})
    executor = _executor(**{service_name: service})

    assert await getattr(executor, executor_method)({}) == {
        "success": False,
        "messages": "fail: service down",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("executor_method", "create_method", "ensure_kwargs"),
    [
        ("create_a_user", "create_a_user", {"exist": False}),
        (
            "create_new_conversation",
            "create_conversation",
            {},
        ),
    ],
)
async def test_create_handlers_check_user_then_create(
    executor_method,
    create_method,
    ensure_kwargs,
):
    payload = {"user_uid": "user-1"}
    created = {"success": True, "messages": "created"}
    ensure = AsyncMock(return_value={"success": True})
    create = AsyncMock(return_value=created)
    data_store = SimpleNamespace(
        ensure_user_exists=ensure,
        **{create_method: create},
    )
    executor = _executor(data_store=data_store)

    assert await getattr(executor, executor_method)(payload) == created
    ensure.assert_awaited_once_with(payload, **ensure_kwargs)
    create.assert_awaited_once_with(payload)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("executor_method", "create_method"),
    [
        ("create_a_user", "create_a_user"),
        ("create_new_conversation", "create_conversation"),
    ],
)
async def test_create_handlers_short_circuit_and_normalize_exception(
    executor_method,
    create_method,
):
    failure = {"success": False, "messages": "missing user"}
    ensure = AsyncMock(return_value=failure)
    create = AsyncMock()
    data_store = SimpleNamespace(
        ensure_user_exists=ensure,
        **{create_method: create},
    )
    executor = _executor(data_store=data_store)

    assert await getattr(executor, executor_method)({}) == failure
    create.assert_not_awaited()

    ensure.side_effect = RuntimeError("lookup failed")
    assert await getattr(executor, executor_method)({}) == {
        "success": False,
        "messages": "fail: lookup failed",
    }


@pytest.mark.asyncio
async def test_update_conversation_expires_deleted_conversation_cache():
    payload = {
        "conversation_uid": "conversation-1",
        "is_deleted": True,
        "task_hash": "internal",
    }
    cache_store = SimpleNamespace(expire_immediately=AsyncMock())
    data_store = SimpleNamespace(
        update_conversation=AsyncMock(
            return_value={"success": True, "messages": "updated"}
        )
    )
    executor = _executor(
        data_store=data_store,
        cache_store=cache_store,
    )

    result = await executor.update_conversation(payload)

    assert result["success"] is True
    cache_store.expire_immediately.assert_awaited_once_with(
        {
            "conversation_uid": "conversation-1",
            "is_deleted": True,
        }
    )
    data_store.update_conversation.assert_awaited_once_with(payload)


@pytest.mark.asyncio
async def test_update_conversation_skips_cache_and_normalizes_failure():
    payload = {"is_deleted": False}
    cache_store = SimpleNamespace(expire_immediately=AsyncMock())
    data_store = SimpleNamespace(
        update_conversation=AsyncMock(
            return_value={"success": True, "messages": "updated"}
        )
    )
    executor = _executor(
        data_store=data_store,
        cache_store=cache_store,
    )

    assert (await executor.update_conversation(payload))["success"] is True
    cache_store.expire_immediately.assert_not_awaited()

    data_store.update_conversation.side_effect = RuntimeError("update failed")
    assert await executor.update_conversation(payload) == {
        "success": False,
        "messages": "fail: update failed",
    }


@pytest.mark.asyncio
async def test_append_message_persists_updates_cache_and_branch_chain():
    payload = {
        "user_uid": "user-1",
        "conversation_uid": "conversation-1",
        "messages": {
            "role": "user",
            "node_id": "node-1",
            "parent_id": "-",
        },
    }
    data_store = SimpleNamespace(
        append_message=AsyncMock(
            return_value={
                "success": True,
                "messages": {
                    "msg_cursor": 3,
                    "id": "message-1",
                },
            }
        )
    )
    cache_store = SimpleNamespace(
        append_messages=AsyncMock(),
        update_current_messages_branch_chain_cache=AsyncMock(),
    )
    executor = _executor(
        data_store=data_store,
        cache_store=cache_store,
    )

    assert await executor.append_message(payload) == {
        "success": True,
        "messages": "success",
    }
    cached_message = payload["messages"]
    assert cached_message["msg_cursor"] == 3
    assert cached_message["id"] == "message-1"
    assert cached_message["is_deleted"] is False
    cache_store.append_messages.assert_awaited_once_with(payload)
    cache_store.update_current_messages_branch_chain_cache.assert_awaited_once_with(
        {
            "user_uid": "user-1",
            "conversation_uid": "conversation-1",
            "node_id": "node-1",
            "parent_id": "-",
        }
    )


@pytest.mark.asyncio
async def test_append_message_short_circuits_and_ignores_cache_append_error():
    payload = {
        "user_uid": "user-1",
        "conversation_uid": "conversation-1",
        "messages": {},
    }
    failure = {"success": False, "messages": "write failed"}
    data_store = SimpleNamespace(
        append_message=AsyncMock(return_value=failure)
    )
    cache_store = SimpleNamespace(
        append_messages=AsyncMock(),
        update_current_messages_branch_chain_cache=AsyncMock(),
    )
    executor = _executor(
        data_store=data_store,
        cache_store=cache_store,
    )

    assert await executor.append_message(deepcopy(payload)) == failure
    cache_store.append_messages.assert_not_awaited()

    data_store.append_message.return_value = {
        "success": True,
        "messages": {"msg_cursor": 1},
    }
    cache_store.append_messages.side_effect = RuntimeError("cache down")

    assert (await executor.append_message(payload))["success"] is True
    cache_store.update_current_messages_branch_chain_cache.assert_awaited_once()


@pytest.mark.asyncio
async def test_append_message_normalizes_outer_exception():
    executor = _executor(
        data_store=SimpleNamespace(append_message=AsyncMock()),
        cache_store=SimpleNamespace(),
    )

    assert await executor.append_message({}) == {
        "success": False,
        "messages": "fail: 'messages'",
    }


@pytest.mark.asyncio
async def test_delete_messages_deletes_related_memory_ids():
    payload = {
        "user_uid": "user-1",
        "conversation_uid": "conversation-1",
    }
    data_store = SimpleNamespace(
        delete_messages=AsyncMock(
            return_value={
                "success": True,
                "messages": [
                    {"id": ""},
                    {"other": "missing"},
                    {"id": "memory-1"},
                ],
            }
        ),
        delete_shortterm_memory=AsyncMock(
            return_value={"success": True}
        ),
    )
    cache_store = SimpleNamespace(expire_immediately=AsyncMock())
    executor = _executor(
        data_store=data_store,
        cache_store=cache_store,
    )

    assert await executor.delete_messages(payload) == {
        "success": True,
        "messages": "success",
    }
    cache_store.expire_immediately.assert_awaited_once_with(payload)
    data_store.delete_shortterm_memory.assert_awaited_once_with(
        {
            "user_uid": "user-1",
            "conversation_uid": "conversation-1",
            "memory_ids": ["memory-1"],
        }
    )


@pytest.mark.asyncio
async def test_delete_messages_handles_cache_store_and_memory_failures():
    payload = {"user_uid": "user-1"}
    delete_messages = AsyncMock(
        return_value={"success": True, "messages": None}
    )
    delete_memory = AsyncMock()
    cache_store = SimpleNamespace(
        expire_immediately=AsyncMock(side_effect=RuntimeError("cache down"))
    )
    data_store = SimpleNamespace(
        delete_messages=delete_messages,
        delete_shortterm_memory=delete_memory,
    )
    executor = _executor(
        data_store=data_store,
        cache_store=cache_store,
    )

    assert (await executor.delete_messages(payload))["success"] is True
    delete_memory.assert_not_awaited()

    failure = {"success": False, "messages": "delete failed"}
    delete_messages.return_value = failure
    assert await executor.delete_messages(payload) == failure

    delete_messages.return_value = {
        "success": True,
        "messages": [{"id": "memory-1"}],
    }
    memory_failure = {"success": False, "messages": "memory failed"}
    delete_memory.return_value = memory_failure
    assert await executor.delete_messages(payload) == memory_failure


@pytest.mark.asyncio
async def test_delete_messages_normalizes_outer_exception():
    executor = _executor(
        data_store=SimpleNamespace(
            delete_messages=AsyncMock(side_effect=RuntimeError("db down"))
        ),
        cache_store=SimpleNamespace(expire_immediately=AsyncMock()),
    )

    assert await executor.delete_messages({}) == {
        "success": False,
        "messages": "fail: db down",
    }


def test_build_visible_messages_handles_empty_input():
    assert _executor()._build_visible_messages(
        [],
        None,
        ("user",),
    ) == ([], {})


def test_build_visible_messages_parses_filters_and_reports_branches():
    rows = [
        _row(
            "node-a",
            "-",
            1,
            "user",
            extra='{"source": "json"}',
            info="invalid-json",
        ),
        _row(
            "node-a",
            "-",
            2,
            "ai",
            extra="invalid-json",
            info='{"score": 1}',
        ),
        _row("node-a", "-", 3, "internal"),
        _row("node-b", "-", 4, "user"),
        _row("node-c", "node-a", 5, "tool", extra="", info=""),
        _row("node-c", "node-a", 6, "tool", deleted=True),
    ]
    executor = _executor()

    parsed, branches, node_chain = executor._build_visible_messages(
        rows,
        "node-a",
        ("user", "ai", "tool"),
    )

    assert [message["msg_cursor"] for message in parsed] == [1, 2, 5]
    assert parsed[0]["extra"] == {"source": "json"}
    assert parsed[0]["info"] == {}
    assert parsed[1]["extra"] == {}
    assert parsed[1]["info"] == {"score": 1}
    assert parsed[2]["extra"] == ""
    assert parsed[2]["info"] == ""
    assert node_chain == ["node-a", "node-c"]
    assert branches == {
        "-": [
            {"node_id": "node-a", "cursor": 1},
            {"node_id": "node-b", "cursor": 4},
        ]
    }


def test_build_visible_messages_strict_path_and_deleted_fallback():
    rows = [
        _row("parent", "-", 1, "user"),
        _row("deleted", "parent", 2, "ai", deleted=True),
        _row("future", "parent", 3, "user"),
    ]
    executor = _executor()

    parsed, branches, node_chain = executor._build_visible_messages(
        rows,
        "deleted",
        ("user", "ai"),
        guess_children=False,
    )

    assert [message["node_id"] for message in parsed] == ["parent"]
    assert branches == {}
    assert node_chain == ["parent"]

    parsed, _, _ = executor._build_visible_messages(
        deepcopy(rows),
        "missing",
        ("user", "ai"),
        guess_children=False,
    )
    assert [message["node_id"] for message in parsed] == [
        "parent",
        "future",
    ]


def test_build_visible_messages_handles_missing_visible_and_cutoff_nodes(
    monkeypatch,
):
    class DivergentNodeMap(dict):
        def __contains__(self, key):
            return True

        def get(self, key, default=None):
            return None

    class MissingNodeHelper:
        def __init__(self, messages):
            self.node_map = DivergentNodeMap()

        def find_nearest_visible(self, node_id):
            return None

        def get_path(self, node_id):
            return []

        def flatten_branch(self, branch):
            return []

    monkeypatch.setattr(
        execute_module,
        "MessageNodeHelper",
        MissingNodeHelper,
    )

    assert _executor()._build_visible_messages(
        [{"raw": True}],
        "missing",
        ("user",),
        guess_children=False,
    ) == ([], {}, [])


def test_build_visible_messages_skips_duplicate_branch_parents(monkeypatch):
    branch = [
        {"node_id": "first", "parent_id": "same-parent"},
        {"node_id": "second", "parent_id": "same-parent"},
    ]

    class DuplicateParentHelper:
        def __init__(self, messages):
            self.node_map = {"first": branch[0]}

        def find_nearest_visible(self, node_id):
            return branch[0]

        def build_branch(self, node_id):
            return branch

        def flatten_branch(self, built_branch):
            return []

        def get_children(self, parent_id):
            return []

    monkeypatch.setattr(
        execute_module,
        "MessageNodeHelper",
        DuplicateParentHelper,
    )

    assert _executor()._build_visible_messages(
        [{"raw": True}],
        "first",
        ("user",),
    ) == ([], {}, [])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "expected_roles", "expected_guess"),
    [
        (
            "get_messages",
            ("user", "ai", "system", "tool", "info"),
            False,
        ),
        ("get_messages_for_user", ("user", "ai", "info"), True),
    ],
)
async def test_get_messages_uses_cached_chain_and_recent_messages(
    method_name,
    expected_roles,
    expected_guess,
):
    payload = {
        "user_uid": "user-1",
        "conversation_uid": "conversation-1",
        "current_node_id": "-",
    }
    cache_store = SimpleNamespace(
        get_current_messages_branch_chain=AsyncMock(
            return_value={
                "success": True,
                "cache_hit": True,
                "messages": ["-", "cached-leaf"],
            }
        ),
        get_recent_messages=AsyncMock(
            return_value={
                "success": True,
                "cache_hit": True,
                "messages": [{"raw": True}],
            }
        ),
        cache_current_messages_branch_chain=AsyncMock(),
    )
    executor = _executor(cache_store=cache_store)
    executor._build_visible_messages = Mock(
        return_value=(
            [{"parsed": True}],
            {"-": [{"node_id": "branch"}]},
            ["-", "cached-leaf"],
        )
    )

    result = await getattr(executor, method_name)(payload)

    assert result["messages"] == [{"parsed": True}]
    assert result["branches"] == {"-": [{"node_id": "branch"}]}
    assert payload["node_id_chain"] == ["-", "cached-leaf"]
    executor._build_visible_messages.assert_called_once_with(
        [{"raw": True}],
        "cached-leaf",
        allow_roles=expected_roles,
        **(
            {"guess_children": expected_guess}
            if method_name == "get_messages"
            else {}
        ),
    )
    cache_store.cache_current_messages_branch_chain.assert_awaited_once_with(
        payload
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "chain_response"),
    [
        (
            "get_messages",
            {"success": False, "cache_hit": True, "messages": ["ignored"]},
        ),
        (
            "get_messages",
            {"success": True, "cache_hit": True, "messages": []},
        ),
        (
            "get_messages_for_user",
            {"success": False, "cache_hit": True, "messages": ["ignored"]},
        ),
        (
            "get_messages_for_user",
            {"success": True, "cache_hit": True, "messages": []},
        ),
    ],
)
async def test_get_messages_ignores_unusable_cached_chains(
    method_name,
    chain_response,
):
    payload = {
        "user_uid": "user-1",
        "conversation_uid": "conversation-1",
        "current_node_id": "-",
    }
    cache_store = SimpleNamespace(
        get_current_messages_branch_chain=AsyncMock(
            return_value=chain_response
        ),
        get_recent_messages=AsyncMock(
            return_value={
                "success": True,
                "cache_hit": True,
                "messages": [{"raw": True}],
            }
        ),
        cache_current_messages_branch_chain=AsyncMock(),
    )
    executor = _executor(cache_store=cache_store)
    executor._build_visible_messages = Mock(
        return_value=([{"parsed": True}], {}, [])
    )

    result = await getattr(executor, method_name)(payload)

    assert result["messages"] == [{"parsed": True}]
    assert executor._build_visible_messages.call_args.args[1] == "-"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method_name",
    ["get_messages", "get_messages_for_user"],
)
async def test_get_messages_falls_back_to_database_and_tolerates_cache_errors(
    method_name,
):
    payload = {
        "user_uid": "user-1",
        "conversation_uid": "conversation-1",
        "current_node_id": "-",
    }
    raw_messages = [{"raw": True}]
    cache_store = SimpleNamespace(
        get_current_messages_branch_chain=AsyncMock(
            side_effect=RuntimeError("chain cache down")
        ),
        get_recent_messages=AsyncMock(
            return_value={"success": True, "cache_hit": False}
        ),
        backfill_messages=AsyncMock(
            side_effect=RuntimeError("message cache down")
        ),
        cache_current_messages_branch_chain=AsyncMock(),
    )
    data_store = SimpleNamespace(
        fetch_messages_after_cursor=AsyncMock(
            return_value={
                "success": True,
                "messages": raw_messages,
            }
        )
    )
    executor = _executor(
        data_store=data_store,
        cache_store=cache_store,
    )
    executor._build_visible_messages = Mock(
        return_value=(
            [{"parsed": True}],
            {},
            ["node-1"],
        )
    )

    result = await getattr(executor, method_name)(payload)

    assert result["messages"] == [{"parsed": True}]
    assert payload["node_id_chain"] == ["node-1"]
    data_store.fetch_messages_after_cursor.assert_awaited_once_with(
        {
            "user_uid": "user-1",
            "conversation_uid": "conversation-1",
            "current_node_id": "-",
            "cursor": 1,
        }
    )
    cache_store.backfill_messages.assert_awaited_once_with(
        {
            "user_uid": "user-1",
            "conversation_uid": "conversation-1",
            "current_node_id": "-",
            "messages": raw_messages,
        }
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method_name",
    ["get_messages", "get_messages_for_user"],
)
async def test_get_messages_returns_database_failure_or_empty_result(
    method_name,
):
    payload = {"current_node_id": "known"}
    cache_store = SimpleNamespace(
        get_recent_messages=AsyncMock(
            return_value={"success": False, "cache_hit": False}
        )
    )
    failure = {"success": False, "messages": "db failed"}
    data_store = SimpleNamespace(
        fetch_messages_after_cursor=AsyncMock(return_value=failure)
    )
    executor = _executor(
        data_store=data_store,
        cache_store=cache_store,
    )

    assert await getattr(executor, method_name)(payload.copy()) == failure

    empty = {"success": True, "messages": []}
    data_store.fetch_messages_after_cursor.return_value = empty
    cache_store.get_recent_messages.return_value = {
        "success": True,
        "cache_hit": False,
    }
    assert await getattr(executor, method_name)(payload.copy()) == empty


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method_name",
    ["get_messages", "get_messages_for_user"],
)
async def test_get_messages_normalizes_outer_exception(method_name):
    executor = _executor(
        cache_store=SimpleNamespace(
            get_recent_messages=AsyncMock(
                side_effect=RuntimeError("cache read failed")
            )
        )
    )

    assert await getattr(executor, method_name)(
        {"current_node_id": "known"}
    ) == {
        "success": False,
        "messages": "fail: cache read failed",
    }


@pytest.mark.asyncio
async def test_insert_skills_returns_database_metadata_failure():
    failure = {"success": False, "messages": "metadata failed"}
    executor = _executor(
        data_store=SimpleNamespace(
            ensure_user_exists=AsyncMock(return_value={"success": True}),
            insert_skill_info=AsyncMock(return_value=failure),
        ),
        file_server=SimpleNamespace(
            handle_skill_package=AsyncMock(
                return_value={
                    "success": True,
                    "messages": [{"skill_id": "skill-1"}],
                }
            )
        ),
    )

    assert await executor.insert_skills({"user_uid": "user-1"}) == failure


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "store_method", "id_key"),
    [
        ("create_llm_provider", "create_llm_provider", "provider_id"),
        ("create_mcp_server", "create_mcp_server", "mcp_id"),
        ("create_cron_task", "create_cron_task", "task_id"),
    ],
)
async def test_create_metadata_handlers_generate_ids(
    method_name,
    store_method,
    id_key,
    monkeypatch,
):
    monkeypatch.setattr(
        execute_module,
        "uuid4",
        lambda: SimpleNamespace(hex="fixed-id"),
    )
    handler = AsyncMock(
        return_value={"success": True, "messages": "created"}
    )
    payload = {"name": "demo"}
    executor = _executor(
        data_store=SimpleNamespace(**{store_method: handler})
    )

    assert (await getattr(executor, method_name)(payload))["success"] is True
    assert payload[id_key] == "fixed-id"
    handler.assert_awaited_once_with(payload)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "store_method"),
    [
        ("create_llm_provider", "create_llm_provider"),
        ("create_mcp_server", "create_mcp_server"),
        ("create_cron_task", "create_cron_task"),
    ],
)
async def test_create_metadata_handlers_normalize_exceptions(
    method_name,
    store_method,
):
    executor = _executor(
        data_store=SimpleNamespace(
            **{
                store_method: AsyncMock(
                    side_effect=RuntimeError("create failed")
                )
            }
        )
    )

    result = await getattr(executor, method_name)({})

    assert result == {
        "success": False,
        "messages": "fail: create failed",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "store_method"),
    [
        ("get_llm_providers", "get_llm_providers"),
        ("get_llm_provider_by_id", "get_llm_provider_by_id"),
    ],
)
async def test_llm_provider_readers_parse_model_lists(
    method_name,
    store_method,
):
    records = [
        {"provider_id": "one", "model_list": ["model-a"]},
        {"provider_id": "two", "model_list": '["model-b"]'},
        {"provider_id": "three", "model_list": None},
    ]
    handler = AsyncMock(
        return_value={"success": True, "messages": records}
    )
    executor = _executor(
        data_store=SimpleNamespace(**{store_method: handler})
    )

    result = await getattr(executor, method_name)({})

    assert result["messages"][0]["model_list"] == ["model-a"]
    assert result["messages"][1]["model_list"] == ["model-b"]
    assert result["messages"][2]["model_list"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "store_method"),
    [
        ("get_llm_providers", "get_llm_providers"),
        ("get_llm_provider_by_id", "get_llm_provider_by_id"),
    ],
)
async def test_llm_provider_readers_return_failures_and_parse_errors(
    method_name,
    store_method,
):
    failure = {"success": False, "messages": "query failed"}
    handler = AsyncMock(return_value=failure)
    executor = _executor(
        data_store=SimpleNamespace(**{store_method: handler})
    )

    assert await getattr(executor, method_name)({}) == failure

    handler.return_value = {
        "success": True,
        "messages": [{"model_list": "invalid-json"}],
    }
    assert await getattr(executor, method_name)({}) == {
        "success": False,
        (
            "messages"
        ): "fail: Expecting value: line 1 column 1 (char 0)",
    }

    handler.side_effect = RuntimeError("query crashed")
    assert await getattr(executor, method_name)({}) == {
        "success": False,
        "messages": "fail: query crashed",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "store_method"),
    [
        ("get_mcp_servers", "get_mcp_servers"),
        ("get_enabled_mcp_servers", "get_enabled_mcp_servers"),
    ],
)
async def test_mcp_readers_parse_configs_and_recover_invalid_json(
    method_name,
    store_method,
):
    records = [
        {"mcp_id": "dict", "config": {"url": "local"}},
        {"mcp_id": "list", "config": ["one"]},
        {"mcp_id": "valid", "config": '{"url": "remote"}'},
        {"mcp_id": "invalid", "config": "invalid-json"},
        {"mcp_id": "empty", "config": None},
    ]
    handler = AsyncMock(
        return_value={"success": True, "messages": records}
    )
    executor = _executor(
        data_store=SimpleNamespace(**{store_method: handler})
    )

    result = await getattr(executor, method_name)({})

    assert result["messages"][0]["config"] == {"url": "local"}
    assert result["messages"][1]["config"] == ["one"]
    assert result["messages"][2]["config"] == {"url": "remote"}
    assert result["messages"][3]["config"] == {}
    assert result["messages"][4]["config"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "store_method"),
    [
        ("get_mcp_servers", "get_mcp_servers"),
        ("get_enabled_mcp_servers", "get_enabled_mcp_servers"),
    ],
)
async def test_mcp_readers_return_store_failure_and_exception(
    method_name,
    store_method,
):
    failure = {"success": False, "messages": "query failed"}
    handler = AsyncMock(return_value=failure)
    executor = _executor(
        data_store=SimpleNamespace(**{store_method: handler})
    )

    assert await getattr(executor, method_name)({}) == failure

    handler.side_effect = RuntimeError("query crashed")
    assert await getattr(executor, method_name)({}) == {
        "success": False,
        "messages": "fail: query crashed",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "store_method"),
    [
        (
            "get_all_enabled_cron_tasks",
            "get_all_enabled_cron_tasks",
        ),
        ("get_cron_tasks", "get_cron_tasks"),
        ("get_cron_task_by_id", "get_cron_task_by_id"),
    ],
)
async def test_cron_readers_parse_extra_config_and_recover_invalid_json(
    method_name,
    store_method,
):
    records = [
        {"task_id": "dict", "extra_config": {"retry": 1}},
        {"task_id": "list", "extra_config": ["one"]},
        {"task_id": "valid", "extra_config": '{"retry": 2}'},
        {"task_id": "invalid", "extra_config": "invalid-json"},
        {"task_id": "empty", "extra_config": None},
    ]
    handler = AsyncMock(
        return_value={"success": True, "messages": records}
    )
    executor = _executor(
        data_store=SimpleNamespace(**{store_method: handler})
    )

    result = await getattr(executor, method_name)({})

    assert result["messages"][0]["extra_config"] == {"retry": 1}
    assert result["messages"][1]["extra_config"] == ["one"]
    assert result["messages"][2]["extra_config"] == {"retry": 2}
    assert result["messages"][3]["extra_config"] == {}
    assert result["messages"][4]["extra_config"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "store_method"),
    [
        (
            "get_all_enabled_cron_tasks",
            "get_all_enabled_cron_tasks",
        ),
        ("get_cron_tasks", "get_cron_tasks"),
        ("get_cron_task_by_id", "get_cron_task_by_id"),
    ],
)
async def test_cron_readers_return_store_failure_and_exception(
    method_name,
    store_method,
):
    failure = {"success": False, "messages": "query failed"}
    handler = AsyncMock(return_value=failure)
    executor = _executor(
        data_store=SimpleNamespace(**{store_method: handler})
    )

    assert await getattr(executor, method_name)({}) == failure

    handler.side_effect = RuntimeError("query crashed")
    assert await getattr(executor, method_name)({}) == {
        "success": False,
        "messages": "fail: query crashed",
    }
