import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from apix.agent.store.core.data_server_manager import (
    DataServerManager,
    data_server_manager as dsm,
)
from apix.common.lifespan.auto_init import auto_init


def make_dependencies():
    cache_store = SimpleNamespace(
        append_message=AsyncMock(return_value={"success": True}),
        expire_immediately=AsyncMock(return_value={"success": True}),
        update_current_messages_branch_chain_cache=AsyncMock(
            return_value={"success": True}
        ),
    )
    data_store = SimpleNamespace(
        ensure_user_exists=AsyncMock(
            return_value={"success": True, "messages": "success"}
        ),
        create_conversation=AsyncMock(
            return_value={"success": True, "messages": "conversation-1"}
        ),
    )
    return cache_store, data_store, SimpleNamespace(), SimpleNamespace()


def make_manager(worker_count=2):
    cache_store, data_store, file_server, rag_server = make_dependencies()
    manager = DataServerManager(
        cache_store=cache_store,
        data_store=data_store,
        file_server=file_server,
        rag_server=rag_server,
        worker_count=worker_count,
    )
    return manager, cache_store, data_store


@pytest.fixture
async def manager():
    instance, _, _ = make_manager()
    try:
        yield instance
    finally:
        await instance.stop()


def test_module_singleton_is_import_safe_and_registered_for_lifecycle():
    assert isinstance(dsm, DataServerManager)
    assert dsm in auto_init._services
    assert dsm._workers == []
    assert "create_new_conversation" in dsm._handle


def test_constructor_registers_executor_handlers_and_validates_worker_count():
    manager, _, _ = make_manager(worker_count=3)

    assert manager._worker_count == 3
    assert manager._workers == []
    assert {
        "create_a_user",
        "create_new_conversation",
        "append_message",
        "upload_file_to_workspace",
        "create_cron_task",
        "upload_file_to_workspace",
        "insert_skills",
        "update_skill",
        "fetch_skills",
        "fetch_target_skill",
        "fetch_longterm_memory",
        "insert_longterm_memory",
        "update_longterm_memory",
    }.issubset(manager._handle)

    with pytest.raises(ValueError, match="greater than zero"):
        make_manager(worker_count=0)


@pytest.mark.asyncio
async def test_start_and_stop_are_idempotent_and_restartable(manager):
    await manager.start()
    original_workers = list(manager._workers)

    await manager.start()

    assert manager._workers == original_workers
    assert len(manager._workers) == 2
    assert {worker.get_name() for worker in manager._workers} == {
        "data-server-worker-0",
        "data-server-worker-1",
    }

    await manager.stop()
    await manager.stop()
    assert manager._workers == []

    manager.handle_register(
        "ping", AsyncMock(return_value={"success": True, "messages": "pong"})
    )
    query_id = await manager.submit_query("ping", {})
    assert await manager.wait_result(query_id) == {
        "success": True,
        "messages": "pong",
    }
    assert len(manager._workers) == 2


@pytest.mark.asyncio
async def test_submit_and_wait_matches_public_usage_example(monkeypatch):
    manager, _, data_store = make_manager(worker_count=1)
    monkeypatch.setattr(
        "apix.agent.store.core.data_server_manager.uuid.uuid4",
        lambda: "fixed-query-id",
    )
    payload = {
        "user_uid": "user-1",
        "platform": "web",
        "title": "A conversation",
        "workspace": "/workspace/demo",
    }

    try:
        query_id = await manager.submit_query(
            action="create_new_conversation",
            payload=payload,
        )
        result = await manager.wait_result(query_id)
    finally:
        await manager.stop()

    assert query_id == "fixed-query-id"
    assert result == {"success": True, "messages": "conversation-1"}
    data_store.ensure_user_exists.assert_awaited_once_with(payload)
    data_store.create_conversation.assert_awaited_once_with(payload)
    assert query_id not in manager._results
    assert manager._queue.empty()


@pytest.mark.asyncio
async def test_executor_short_circuit_is_returned_to_waiter():
    manager, _, data_store = make_manager(worker_count=1)
    data_store.ensure_user_exists.return_value = {
        "success": False,
        "messages": "user missing",
    }

    try:
        query_id = await manager.submit_query(
            "create_new_conversation", {"user_uid": "missing"}
        )
        result = await manager.wait_result(query_id)
    finally:
        await manager.stop()

    assert result == {"success": False, "messages": "user missing"}
    data_store.create_conversation.assert_not_awaited()


@pytest.mark.asyncio
async def test_custom_handler_registration_and_replacement(manager):
    first = AsyncMock(return_value={"source": "first"})
    replacement = AsyncMock(return_value={"source": "replacement"})
    manager.handle_register("custom", first)
    manager.handle_register("custom", replacement)
    payload = {"value": 42}

    query_id = await manager.submit_query("custom", payload)
    result = await manager.wait_result(query_id)

    assert result == {"source": "replacement"}
    first.assert_not_awaited()
    replacement.assert_awaited_once_with(payload)


@pytest.mark.asyncio
async def test_unknown_action_returns_structured_failure(manager):
    query_id = await manager.submit_query("does_not_exist", {"value": 1})

    result = await manager.wait_result(query_id)

    assert result == {
        "success": False,
        "messages": "unknown action: does_not_exist",
    }


@pytest.mark.asyncio
async def test_handler_exception_isolated_by_worker(manager):
    handler = AsyncMock(side_effect=RuntimeError("handler exploded"))
    manager.handle_register("explode", handler)

    query_id = await manager.submit_query("explode", {"value": 1})
    result = await manager.wait_result(query_id)

    assert result == {
        "success": False,
        "messages": "internal error: handler exploded",
    }
    assert all(not worker.done() for worker in manager._workers)


@pytest.mark.asyncio
async def test_wait_result_rejects_unknown_or_already_consumed_query(manager):
    with pytest.raises(KeyError, match="Unknown query_id: missing"):
        await manager.wait_result("missing")

    manager.handle_register("ok", AsyncMock(return_value="done"))
    query_id = await manager.submit_query("ok", {})
    assert await manager.wait_result(query_id) == "done"

    with pytest.raises(KeyError, match=f"Unknown query_id: {query_id}"):
        await manager.wait_result(query_id)


@pytest.mark.asyncio
async def test_multiple_workers_execute_queries_concurrently():
    manager, _, _ = make_manager(worker_count=2)
    both_started = asyncio.Event()
    release = asyncio.Event()
    started_payloads = []

    async def blocking_handler(payload):
        started_payloads.append(payload["id"])
        if len(started_payloads) == 2:
            both_started.set()
        await release.wait()
        return {"success": True, "messages": payload["id"]}

    manager.handle_register("blocking", blocking_handler)

    try:
        first_id = await manager.submit_query("blocking", {"id": 1})
        second_id = await manager.submit_query("blocking", {"id": 2})
        await asyncio.wait_for(both_started.wait(), timeout=1)
        assert set(started_payloads) == {1, 2}

        release.set()
        results = await asyncio.gather(
            manager.wait_result(first_id),
            manager.wait_result(second_id),
        )
        await asyncio.wait_for(manager._queue.join(), timeout=1)
    finally:
        release.set()
        await manager.stop()

    assert {result["messages"] for result in results} == {1, 2}
    assert manager._results == {}


@pytest.mark.asyncio
async def test_wait_timeout_cleans_result_and_cancelled_query_is_not_reused(manager):
    entered = asyncio.Event()
    never_release = asyncio.Event()

    async def slow_handler(payload):
        entered.set()
        await never_release.wait()
        return payload

    manager.handle_register("slow", slow_handler)
    query_id = await manager.submit_query("slow", {"value": 1})
    await entered.wait()

    with pytest.raises(TimeoutError):
        await asyncio.wait_for(manager.wait_result(query_id), timeout=0.01)

    assert query_id not in manager._results
    with pytest.raises(KeyError, match=f"Unknown query_id: {query_id}"):
        await manager.wait_result(query_id)


@pytest.mark.asyncio
async def test_stop_cancels_pending_result_drains_queue_and_allows_restart():
    manager, _, _ = make_manager(worker_count=1)
    entered = asyncio.Event()
    never_release = asyncio.Event()

    async def slow_handler(payload):
        entered.set()
        await never_release.wait()
        return payload

    manager.handle_register("slow", slow_handler)
    active_id = await manager.submit_query("slow", {"value": "active"})
    queued_id = await manager.submit_query("slow", {"value": "queued"})
    active_waiter = asyncio.create_task(manager.wait_result(active_id))
    queued_waiter = asyncio.create_task(manager.wait_result(queued_id))
    await entered.wait()

    await manager.stop()

    with pytest.raises(asyncio.CancelledError):
        await active_waiter
    with pytest.raises(asyncio.CancelledError):
        await queued_waiter
    assert manager._workers == []
    assert manager._results == {}
    assert manager._queue.empty()
    assert manager._queue._unfinished_tasks == 0

    manager.handle_register("fast", AsyncMock(return_value="restarted"))
    restarted_id = await manager.submit_query("fast", {})
    assert await manager.wait_result(restarted_id) == "restarted"
    await manager.stop()
