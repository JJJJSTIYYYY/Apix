from unittest.mock import AsyncMock, Mock

import pytest

from apix.agent.store.core.server.cache_store.cache_server_base import CacheServerBase
from apix.agent.store.core.server.cache_store import utils as cache_utils
from apix.agent.store.core.server.cache_store.utils import cache_store_handler
from apix.agent.store.core.server.data_store import data_server_base as data_base_module
from apix.agent.store.core.server.data_store import utils as data_utils
from apix.agent.store.core.server.data_store.data_server_base import DataServerBase
from apix.agent.store.core.server.data_store.utils import data_store_handler


class ConcreteCacheServer(CacheServerBase):
    append_message = AsyncMock()
    backfill_messages = AsyncMock()
    get_recent_messages = AsyncMock()
    cache_current_messages_branch_chain = AsyncMock()
    update_current_messages_branch_chain_cache = AsyncMock()
    get_current_messages_branch_chain = AsyncMock()
    backfill_resource = AsyncMock()
    get_resource = AsyncMock()
    invalidate_resource = AsyncMock()
    set_expire = AsyncMock()
    expire_immediately = AsyncMock()


class ConcreteDataServer(DataServerBase):
    async def create_a_user(self, payload): ...
    async def verify_user(self, payload): ...
    async def ensure_user_exists(self, payload, exist=True): ...
    async def fetch_conversation_list(self, payload): ...
    async def get_conversation_meta_by_id(self, payload): ...
    async def create_conversation(self, payload): ...
    async def update_conversation(self, payload): ...
    async def append_message(self, payload): ...
    async def delete_messages(self, payload): ...
    async def fetch_messages_after_cursor(self, payload): ...
    async def search_messages_by_keyword(self, payload): ...
    async def fetch_shortterm_memory(self, payload): ...
    async def insert_shortterm_memory(self, payload): ...
    async def delete_shortterm_memory(self, payload): ...
    async def fetch_longterm_memory(self, payload): ...
    async def insert_longterm_memory(self, payload): ...
    async def update_longterm_memory(self, payload): ...
    async def create_llm_provider(self, payload): ...
    async def get_llm_providers(self, payload): ...
    async def get_llm_provider_by_id(self, payload): ...
    async def update_llm_provider(self, payload): ...
    async def create_mcp_server(self, payload): ...
    async def get_mcp_servers(self, payload): ...
    async def get_enabled_mcp_servers(self, payload): ...
    async def update_mcp_server(self, payload): ...
    async def create_cron_task(self, payload): ...
    async def get_all_enabled_cron_tasks(self, payload): ...
    async def get_cron_tasks(self, payload): ...
    async def get_cron_task_by_id(self, payload): ...
    async def update_cron_task(self, payload): ...


@pytest.mark.asyncio
async def test_cache_base_lifecycle_and_key_builder():
    service = ConcreteCacheServer()

    await service.start()
    await service.stop()

    assert service._build_memo_key(
        {"user_uid": "u-1", "conversation_uid": "c-1"}
    ) == "memo:u-1:c-1"
    assert service._build_memo_key(
        {"user_uid": "u-1", "conversation_uid": "c-1"}, prefix="chain"
    ) == "chain:u-1:c-1"
    assert service._build_resource_key(
        {"cache_group": "skills:u/1", "cache_key": "list:5"}
    ) == "resource:skills%3Au%2F1:list%3A5"
    assert service._build_resource_prefix(
        {"cache_group": "skills:u/1"}
    ) == "resource:skills%3Au%2F1:"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"user_uid": "u-1"},
        {"conversation_uid": "c-1"},
        {"user_uid": "", "conversation_uid": "c-1"},
    ],
)
def test_cache_key_builder_requires_nonempty_identifiers(payload):
    with pytest.raises(KeyError, match="user_uid and conversation_uid required"):
        ConcreteCacheServer()._build_memo_key(payload)


@pytest.mark.parametrize(
    ("method_name", "payload", "message"),
    [
        ("_build_resource_prefix", {}, "cache_group"),
        ("_build_resource_prefix", {"cache_group": ""}, "cache_group"),
        (
            "_build_resource_key",
            {"cache_group": "skills", "cache_key": ""},
            "cache_key",
        ),
    ],
)
def test_resource_key_builder_requires_nonempty_parts(
    method_name,
    payload,
    message,
):
    with pytest.raises(KeyError, match=message):
        getattr(ConcreteCacheServer(), method_name)(payload)


@pytest.mark.asyncio
async def test_data_base_generates_string_id_and_default_optional_methods(monkeypatch):
    monkeypatch.setattr(data_base_module.idgen, "next_id", lambda: 987654321)
    service = ConcreteDataServer()

    await service.start()
    await service.stop()

    assert service._conversation_id_generator() == "987654321"
    assert await service.insert_skill_info({}) is None
    assert await service.update_skill_status({}) is None
    assert await service.fetch_available_skills({}) is None
    assert await service.fetch_target_skill({}) is None


@pytest.mark.asyncio
async def test_data_store_handler_traces_and_normalizes_failures(monkeypatch):
    trace = Mock()
    exception = Mock()
    monkeypatch.setattr(data_utils.logger, "trace", trace)
    monkeypatch.setattr(data_utils.logger, "exception", exception)

    @data_store_handler
    async def successful(value):
        return {"success": True, "messages": value}

    @data_store_handler
    async def failing():
        raise ValueError("database unavailable")

    @data_store_handler(
        failure_factory=lambda exc: {
            "success": False,
            "messages": {"error": type(exc).__name__},
        }
    )
    async def custom_failure():
        raise KeyError("missing identity")

    assert successful.__name__ == "successful"
    assert await successful("stored") == {
        "success": True,
        "messages": "stored",
    }
    assert await failing() == {
        "success": False,
        "messages": "fail: database unavailable",
    }
    assert await custom_failure() == {
        "success": False,
        "messages": {"error": "KeyError"},
    }
    assert trace.call_count == 3
    assert exception.call_count == 2


@pytest.mark.asyncio
async def test_cache_store_handler_traces_and_normalizes_failures(monkeypatch):
    trace = Mock()
    exception = Mock()
    monkeypatch.setattr(cache_utils.logger, "trace", trace)
    monkeypatch.setattr(cache_utils.logger, "exception", exception)

    @cache_store_handler
    async def successful(value):
        return {"success": True, "messages": value}

    @cache_store_handler
    async def failing():
        raise RuntimeError("cache unavailable")

    assert successful.__name__ == "successful"
    assert await successful("cached") == {
        "success": True,
        "messages": "cached",
    }
    assert await failing() == {
        "success": False,
        "messages": "fail: cache unavailable",
    }
    assert trace.call_count == 2
    exception.assert_called_once()
