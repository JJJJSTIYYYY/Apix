import json
from unittest.mock import Mock

import pytest

from apix.agent.store.core.server.cache_store import redis_server as redis_module
from apix.agent.store.core.server.cache_store.redis_server import RedisService


class FakePipeline:
    def __init__(self, redis):
        self.redis = redis
        self.commands = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def rpush(self, key, *values):
        self.commands.append(("rpush", key, values))
        return self

    def expire(self, key, ttl):
        self.commands.append(("expire", key, ttl))
        return self

    def delete(self, key):
        self.commands.append(("delete", key))
        return self

    async def execute(self):
        for command in self.commands:
            name, key, *args = command
            if name == "delete":
                self.redis.values.pop(key, None)
            elif name == "rpush":
                self.redis.values.setdefault(key, []).extend(args[0])
            elif name == "expire":
                self.redis.expiries[key] = args[0]
        return [True] * len(self.commands)


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.expiries = {}
        self.closed = False

    async def exists(self, key):
        return key in self.values

    def pipeline(self):
        return FakePipeline(self)

    async def lrange(self, key, start, stop):
        return list(self.values.get(key, []))

    async def set(self, key, value, ex=None):
        self.values[key] = value
        self.expiries[key] = ex
        return True

    async def get(self, key):
        return self.values.get(key)

    async def expire(self, key, ttl):
        self.expiries[key] = ttl
        return key in self.values

    async def delete(self, key):
        self.values.pop(key, None)
        return 1

    async def aclose(self):
        self.closed = True


@pytest.fixture
def payload():
    return {"user_uid": "user-1", "conversation_uid": "conversation-1"}


@pytest.fixture
def service():
    instance = RedisService.__new__(RedisService)
    instance._memo_redis = FakeRedis()
    return instance


def test_constructor_configures_async_redis_client(monkeypatch):
    client = object()
    from_url = Mock(return_value=client)
    monkeypatch.setattr(redis_module.redis, "from_url", from_url)

    service = RedisService("redis://cache.example:6379/2")

    assert service._memo_redis is client
    from_url.assert_called_once_with(
        "redis://cache.example:6379/2",
        decode_responses=True,
        max_connections=redis_module.REDIS_POOL_SIZE,
        socket_keepalive=True,
    )


@pytest.mark.asyncio
async def test_lifecycle_closes_client(service):
    await service.start()
    await service.stop()
    assert service._memo_redis.closed is True


@pytest.mark.asyncio
async def test_message_cache_miss_backfill_append_and_read(service, payload):
    assert await service.append_message(
        {**payload, "message": {"message_uid": "message-2"}}
    ) == {
        "success": True,
        "messages": "success",
    }
    assert await service.get_recent_messages(payload) == {
        "success": True,
        "messages": [],
        "cache_hit": False,
    }

    messages = [
        {
            "message_uid": "message-1",
            "content": "你好",
            "metadata": {},
            "extensions": {},
        }
    ]
    assert await service.backfill_messages({**payload, "messages": messages}) == {
        "success": True,
        "messages": "success",
    }
    key = "memo:user-1:conversation-1"
    assert service._memo_redis.expiries[key] == redis_module.HOT_CACHE_DEFAULT_EXPIRE_SECONDS

    await service.append_message(
        {**payload, "message": {"message_uid": "message-2"}}
    )
    assert await service.get_recent_messages(payload) == {
        "success": True,
        "messages": [messages[0], {"message_uid": "message-2"}],
        "cache_hit": True,
    }

    await service.backfill_messages({**payload, "messages": []})
    assert not (await service.get_recent_messages(payload))["cache_hit"]


@pytest.mark.asyncio
async def test_message_backfill_rejects_non_list(service, payload):
    result = await service.backfill_messages({**payload, "messages": {"id": 1}})
    assert result["success"] is False
    assert "Messages must be a list" in result["messages"]


@pytest.mark.asyncio
async def test_branch_chain_workflow_and_statuses(service, payload):
    assert await service.update_current_messages_branch_chain_cache(
        {**payload, "parent_id": "root", "node_id": "leaf"}
    ) == {"success": True, "messages": "cache not found"}

    await service.cache_current_messages_branch_chain(
        {**payload, "node_id_chain": ["root", "old"]}
    )
    chain_key = "chain:user-1:conversation-1"
    assert service._memo_redis.expiries[chain_key] == redis_module.STATIC_CACHE_DEFAULT_EXPIRE_SECONDS
    assert await service.get_current_messages_branch_chain(payload) == {
        "success": True,
        "messages": ["root", "old"],
        "cache_hit": True,
    }
    assert await service.update_current_messages_branch_chain_cache(
        {**payload, "parent_id": "missing", "node_id": "leaf"}
    ) == {"success": True, "messages": "parent_id not found in cache"}
    assert await service.update_current_messages_branch_chain_cache(
        {**payload, "parent_id": "root", "node_id": "old"}
    ) == {"success": True, "messages": "already up to date"}
    assert await service.update_current_messages_branch_chain_cache(
        {**payload, "parent_id": "root", "node_id": "new"}
    ) == {"success": True, "messages": "success"}
    assert json.loads(service._memo_redis.values[chain_key]) == ["root", "new"]


@pytest.mark.asyncio
async def test_branch_chain_validation_and_cache_miss(service, payload):
    invalid = await service.cache_current_messages_branch_chain(
        {**payload, "node_id_chain": "root"}
    )
    assert invalid["success"] is False

    service._memo_redis.values["chain:user-1:conversation-1"] = json.dumps(
        {"not": "a list"}
    )
    invalid_cached = await service.update_current_messages_branch_chain_cache(
        {**payload, "parent_id": "root", "node_id": "leaf"}
    )
    assert invalid_cached["success"] is False

    service._memo_redis.values.clear()
    assert await service.get_current_messages_branch_chain(payload) == {
        "success": True,
        "messages": [],
        "cache_hit": False,
    }


@pytest.mark.asyncio
async def test_ttl_methods(service, payload):
    key = "memo:user-1:conversation-1"
    service._memo_redis.values[key] = []

    assert await service.set_expire(payload, ttl_seconds=42) == {
        "success": True,
        "messages": "success",
    }
    assert service._memo_redis.expiries[key] == 42
    assert await service.expire_immediately(payload) == {
        "success": True,
        "messages": "success",
    }
    assert key not in service._memo_redis.values


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,payload",
    [
        ("get_recent_messages", {"user_uid": "user-1"}),
        ("get_current_messages_branch_chain", {"conversation_uid": "c-1"}),
        ("set_expire", {}),
        ("expire_immediately", {}),
    ],
)
async def test_public_methods_convert_errors_to_failure(service, method, payload):
    result = await getattr(service, method)(payload)
    assert result["success"] is False
    assert result["messages"].startswith("fail:")
