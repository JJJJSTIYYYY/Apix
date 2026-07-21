import json

import pytest

from apix.agent.store.core.server.cache_store import builtin_server as builtin_module
from apix.agent.store.core.server.cache_store.builtin_server import BuiltinService


@pytest.fixture
def payload():
    return {"user_uid": "user-1", "conversation_uid": "conversation-1"}


@pytest.mark.asyncio
async def test_message_cache_workflow_is_copy_safe(tmp_path, payload):
    service = BuiltinService(tmp_path / "cache.json")
    original = [{"role": "user", "content": "hello"}]

    assert await service.backfill_messages({**payload, "messages": original}) == {
        "success": True,
        "messages": "success",
    }
    original[0]["content"] = "mutated outside cache"

    result = await service.get_recent_messages(payload)
    assert result == {
        "success": True,
        "messages": [{"role": "user", "content": "hello"}],
        "cache_hit": True,
    }

    result["messages"][0]["content"] = "mutated result"
    await service.append_messages(
        {**payload, "messages": {"role": "ai", "content": "world"}}
    )
    result = await service.get_recent_messages(payload)
    assert [message["content"] for message in result["messages"]] == [
        "hello",
        "world",
    ]

    assert await service.expire_immediately(payload) == {
        "success": True,
        "messages": "success",
    }
    assert await service.get_recent_messages(payload) == {
        "success": True,
        "messages": [],
        "cache_hit": False,
    }


@pytest.mark.asyncio
async def test_append_is_a_noop_on_cache_miss_and_empty_backfill_clears(
    tmp_path, payload
):
    service = BuiltinService(tmp_path / "cache.json")

    assert (await service.append_messages({**payload, "messages": {"id": 1}}))[
        "success"
    ]
    assert not (await service.get_recent_messages(payload))["cache_hit"]

    await service.backfill_messages({**payload, "messages": [{"id": 1}]})
    await service.backfill_messages({**payload, "messages": []})
    assert not (await service.get_recent_messages(payload))["cache_hit"]


@pytest.mark.asyncio
async def test_ttl_expiry_is_applied_without_sleep(monkeypatch, tmp_path, payload):
    clock = [1000.0]
    monkeypatch.setattr(builtin_module.time, "time", lambda: clock[0])
    service = BuiltinService(tmp_path / "cache.json")

    await service.backfill_messages({**payload, "messages": [{"id": 1}]})
    await service.set_expire(payload, ttl_seconds=10)
    clock[0] = 1009.9
    assert (await service.get_recent_messages(payload))["cache_hit"]
    clock[0] = 1010.0
    assert not (await service.get_recent_messages(payload))["cache_hit"]
    assert service._cache == {}


@pytest.mark.asyncio
async def test_branch_chain_create_update_and_read(tmp_path, payload):
    service = BuiltinService(tmp_path / "cache.json")

    assert await service.cache_current_messages_branch_chain(
        {**payload, "node_id_chain": ["root", "old"]}
    ) == {"success": True, "messages": "success"}
    assert await service.get_current_messages_branch_chain(payload) == {
        "success": True,
        "messages": ["root", "old"],
        "cache_hit": True,
    }
    assert await service.update_current_messages_branch_chain_cache(
        {**payload, "parent_id": "root", "node_id": "new"}
    ) == {"success": True, "messages": "success"}
    assert (await service.get_current_messages_branch_chain(payload))["messages"] == [
        "root",
        "new",
    ]
    assert await service.update_current_messages_branch_chain_cache(
        {**payload, "parent_id": "root", "node_id": "new"}
    ) == {"success": True, "messages": "already up to date"}
    assert await service.update_current_messages_branch_chain_cache(
        {**payload, "parent_id": "missing", "node_id": "other"}
    ) == {"success": True, "messages": "parent_id not found in cache"}


@pytest.mark.asyncio
async def test_branch_chain_update_handles_cache_miss(tmp_path, payload):
    service = BuiltinService(tmp_path / "cache.json")

    assert await service.update_current_messages_branch_chain_cache(
        {**payload, "parent_id": "root", "node_id": "new"}
    ) == {"success": True, "messages": "cache not found"}
    assert await service.get_current_messages_branch_chain(payload) == {
        "success": True,
        "messages": [],
        "cache_hit": False,
    }


@pytest.mark.asyncio
async def test_persistence_restores_only_valid_unexpired_items(
    monkeypatch, tmp_path, payload
):
    clock = [2000.0]
    monkeypatch.setattr(builtin_module.time, "time", lambda: clock[0])
    path = tmp_path / "nested" / "cache.json"
    first = BuiltinService(path)
    await first.backfill_messages({**payload, "messages": [{"id": 1}]})
    await first.cache_current_messages_branch_chain(
        {**payload, "node_id_chain": ["root"]}
    )
    first._cache["expired"] = {"value": "old", "expires_at": 1999.0}
    await first.stop()

    stored = json.loads(path.read_text(encoding="utf-8"))
    assert "expired" not in stored
    restored = BuiltinService(path)
    await restored.start()
    assert (await restored.get_recent_messages(payload))["messages"] == [{"id": 1}]
    assert (await restored.get_current_messages_branch_chain(payload))[
        "messages"
    ] == ["root"]


@pytest.mark.asyncio
@pytest.mark.parametrize("content", ["not json", "[]", '{"bad": {}}'])
async def test_invalid_persistence_is_ignored(tmp_path, content):
    path = tmp_path / "cache.json"
    path.write_text(content, encoding="utf-8")
    service = BuiltinService(path)

    await service.start()

    assert service._cache == {}


@pytest.mark.asyncio
async def test_validation_errors_are_returned_as_failures(tmp_path, payload):
    service = BuiltinService(tmp_path / "cache.json")

    for result in (
        await service.backfill_messages({**payload, "messages": "not-a-list"}),
        await service.cache_current_messages_branch_chain(
            {**payload, "node_id_chain": "not-a-list"}
        ),
        await service.get_recent_messages({"user_uid": "user-1"}),
        await service.update_current_messages_branch_chain_cache(payload),
    ):
        assert result["success"] is False
        assert result["messages"].startswith("fail:")


def test_item_validation_and_purge_helpers(monkeypatch, tmp_path):
    monkeypatch.setattr(builtin_module.time, "time", lambda: 50.0)
    service = BuiltinService(tmp_path / "cache.json")
    service._cache = {
        "valid": {"value": 1, "expires_at": 51.0},
        "expired": {"value": 2, "expires_at": 49.0},
        "malformed": {"value": 3},
    }

    service._purge_expired()

    assert service._cache == {"valid": {"value": 1, "expires_at": 51.0}}
    assert BuiltinService._is_valid_item(service._cache["valid"], 50.0)
    assert not BuiltinService._is_valid_item([], 50.0)
