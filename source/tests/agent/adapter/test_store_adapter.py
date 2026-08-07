from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from apix.agent.sdk.adapter.store import store_adapter as store_module
from apix.agent.sdk.adapter.store.store_adapter import AIStoreAdapter


@pytest.fixture
def identity():
    return {
        "id": "user-1",
        "platform": "web",
        "conversation_uid": "conversation-1",
    }


@pytest.mark.asyncio
async def test_append_message_skips_empty_and_sub_conversation(monkeypatch, identity):
    query = AsyncMock()
    monkeypatch.setattr(store_module, "query_store", query)
    adapter = AIStoreAdapter()

    await adapter.append_message_to_store(None, identity, "generation")
    await adapter.append_message_to_store(
        {"role": "ai"},
        {**identity, "conversation_uid": "sub_worker"},
        "generation",
    )

    query.assert_not_awaited()


@pytest.mark.asyncio
async def test_append_dict_message_and_info_payloads(monkeypatch, identity):
    query = AsyncMock(return_value={"success": True})
    monkeypatch.setattr(store_module, "query_store", query)
    adapter = AIStoreAdapter()
    message = {"message_uid": "message-1", "role": "ai"}

    await adapter.append_message_to_store(message, identity, "generation")
    assert query.await_args.kwargs == {
        "action": "append_message",
        "payload": {
            "user_uid": "user-1",
            "conversation_uid": "conversation-1",
            "messages": message,
        },
    }

    query.reset_mock()
    await adapter.append_info_to_store(
        {"todo_list": []},
        {"provider": "test"},
        identity,
        "12345678-1234-1234-1234-123456789abc",
        parent_id="parent",
        name="todo",
    )
    stored = query.await_args.kwargs["payload"]["messages"]
    assert query.await_args.kwargs["action"] == "append_message"
    assert stored["role"] == "info"
    assert stored["name"] == "todo"
    assert stored["parent_id"] == "parent"
    assert stored["metadata"] == {"provider": "test"}
    assert stored["extensions"] == {"todo_list": []}
    assert len(stored["message_uid"]) == 32


@pytest.mark.asyncio
async def test_append_shortterm_validates_content_and_sends_payload(
    monkeypatch,
    identity,
):
    query = AsyncMock(return_value={"success": True})
    monkeypatch.setattr(store_module, "query_store", query)
    adapter = AIStoreAdapter()

    await adapter.append_shortterm_to_store("   ", identity, "memory-1")
    query.assert_not_awaited()

    await adapter.append_shortterm_to_store(
        "  remember this  ",
        identity,
        "memory-1",
    )
    assert query.await_args.kwargs == {
        "action": "insert_shortterm_memory",
        "payload": {
            "memory_id": "memory-1",
            "user_uid": "user-1",
            "conversation_uid": "conversation-1",
            "content": "remember this",
        },
    }


@pytest.mark.asyncio
async def test_get_messages_returns_latest_chain_or_root(monkeypatch, identity):
    query = AsyncMock(
        side_effect=[
            {"messages": [{"content": "a"}], "current_chain": ["-", "n1"]},
            {"messages": [], "current_chain": []},
        ]
    )
    monkeypatch.setattr(store_module, "query_store", query)
    adapter = AIStoreAdapter()

    assert await adapter.get_messages_from_store(
        identity,
        current_node_id="n0",
        preserved_context_window=10,
    ) == ([{"content": "a"}], "n1")
    assert query.await_args_list[0].kwargs["payload"] == {
        "user_uid": "user-1",
        "conversation_uid": "conversation-1",
        "current_node_id": "n0",
        "cursor": 0,
        "limit": 10,
    }
    assert await adapter.get_messages_from_store(identity) == ([], "-")


@pytest.mark.asyncio
async def test_memory_fetches_return_messages_and_absorb_backend_errors(
    monkeypatch,
    identity,
):
    query = AsyncMock(
        side_effect=[
            {"messages": [{"memory_id": "short"}]},
            RuntimeError("short failed"),
            {"messages": [{"memory_id": "long"}]},
            RuntimeError("long failed"),
        ]
    )
    monkeypatch.setattr(store_module, "query_store", query)
    adapter = AIStoreAdapter()

    assert await adapter.get_shortterm_from_store(identity) == [
        {"memory_id": "short"}
    ]
    assert await adapter.get_shortterm_from_store(identity) == []
    assert await adapter.get_longterm_from_store(
        identity,
        workspace="apix",
    ) == [{"memory_id": "long"}]
    assert query.await_args_list[2].kwargs["payload"]["workspace"] == "apix"
    assert await adapter.get_longterm_from_store(identity) == []


@pytest.mark.asyncio
async def test_get_skills_uses_skill_action_and_filters_inactive(
    monkeypatch,
    identity,
):
    query = AsyncMock(
        side_effect=[
            {
                "messages": [
                    {
                        "skill_id": "s1",
                        "skill_name": "active",
                        "skill_description": "desc",
                        "is_active": True,
                    },
                    {
                        "skill_id": "s2",
                        "skill_name": "inactive",
                        "skill_description": "desc",
                        "is_active": False,
                    },
                ]
            },
            RuntimeError("failed"),
        ]
    )
    monkeypatch.setattr(store_module, "query_store", query)
    adapter = AIStoreAdapter()

    assert await adapter.get_skills_from_store(identity) == [
        {
            "skill_id": "s1",
            "skill_name": "active",
            "description": "desc",
        }
    ]
    assert query.await_args_list[0].kwargs == {
        "action": "fetch_skills",
        "payload": {"user_uid": "user-1", "limit": 999},
    }
    assert await adapter.get_skills_from_store(identity) == []
