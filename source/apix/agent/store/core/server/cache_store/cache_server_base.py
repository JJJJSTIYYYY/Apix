from abc import ABC, abstractmethod

from apix.config.base_config import HOT_CACHE_DEFAULT_EXPIRE_SECONDS


class CacheServerBase(ABC):
    """Cache contract for canonical stored-message dictionaries.

    Message payloads use ``message_uid``, ``name``, ``metadata``,
    ``extensions`` and the database-generated ``timestamp``.  Cache
    implementations must preserve those fields without translating them into
    a second schema.
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
    # TTL
    # ------------------------------------------------------------------

    @abstractmethod
    async def set_expire(self, payload: dict, ttl_seconds: int = HOT_CACHE_DEFAULT_EXPIRE_SECONDS) -> dict:
        pass

    @abstractmethod
    async def expire_immediately(self, payload: dict) -> dict:
        pass
