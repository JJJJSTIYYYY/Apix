from abc import ABC, abstractmethod
from urllib.parse import quote

from apix.config.base_config import HOT_CACHE_DEFAULT_EXPIRE_SECONDS


class CacheServerBase(ABC):
    """Cache contract for messages and read-through resource data.

    Message payloads use ``message_uid``, ``name``, ``metadata``,
    ``extensions`` and the database-generated ``timestamp``.  Cache
    implementations must preserve those fields without translating them into
    a second schema.

    Skills, MCP servers, providers and memory records use the generic
    resource-cache methods. Resource cache entries are disposable read-through
    copies: the data store remains the only source of truth.
    """

    def __init__(self,):
        pass

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Key Builders
    # ------------------------------------------------------------------

    def _build_memo_key(self, payload: dict, prefix: str = 'memo') -> str:
        user_uid = payload.get("user_uid")
        conversation_uid = payload.get("conversation_uid")

        if not all([user_uid, conversation_uid]):
            raise KeyError("user_uid and conversation_uid required")

        return f"{prefix}:{user_uid}:{conversation_uid}"

    def _build_resource_key(self, payload: dict) -> str:
        cache_group = payload.get("cache_group")
        cache_key = payload.get("cache_key")

        if not isinstance(cache_group, str) or not cache_group:
            raise KeyError("non-empty cache_group required")
        if not isinstance(cache_key, str) or not cache_key:
            raise KeyError("non-empty cache_key required")

        return (
            f"{self._build_resource_prefix(payload)}"
            f"{quote(cache_key, safe='')}"
        )

    def _build_resource_prefix(self, payload: dict) -> str:
        cache_group = payload.get("cache_group")
        if not isinstance(cache_group, str) or not cache_group:
            raise KeyError("non-empty cache_group required")
        return f"resource:{quote(cache_group, safe='')}:"

    # ------------------------------------------------------------------
    # Memo Redis (Conversation Cache)
    # ------------------------------------------------------------------

    @abstractmethod
    async def append_message(self, payload: dict) -> dict:
        pass
        
    @abstractmethod
    async def backfill_messages(self, payload: dict) -> dict:
        pass
        
    @abstractmethod
    async def get_recent_messages(self, payload: dict) -> dict:
        pass
        
    @abstractmethod
    async def cache_current_messages_branch_chain(self, payload: dict) -> dict:
        pass
        
    @abstractmethod
    async def update_current_messages_branch_chain_cache(self, payload: dict) -> dict:
        pass
        
    @abstractmethod
    async def get_current_messages_branch_chain(self, payload: dict) -> dict:
        pass

    # ------------------------------------------------------------------
    # Read-through Resource Cache
    # ------------------------------------------------------------------

    @abstractmethod
    async def backfill_resource(self, payload: dict) -> dict:
        """Cache a successful data-store result."""
        pass

    @abstractmethod
    async def get_resource(self, payload: dict) -> dict:
        """Return a cached resource result and an explicit cache-hit flag."""
        pass

    @abstractmethod
    async def invalidate_resource(self, payload: dict) -> dict:
        """Invalidate one resource entry or every entry in a cache group."""
        pass

    # ------------------------------------------------------------------
    # TTL
    # ------------------------------------------------------------------

    @abstractmethod
    async def set_expire(self, payload: dict, ttl_seconds: int = HOT_CACHE_DEFAULT_EXPIRE_SECONDS) -> dict:
        pass

    @abstractmethod
    async def expire_immediately(self, payload: dict) -> dict:
        pass
