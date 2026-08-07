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
        """Initialize the cache service."""
        pass

    async def start(self) -> None:
        """Start the cache service and initialize its resources."""
        pass

    async def stop(self) -> None:
        """Stop the cache service and release its resources."""
        pass

    # ------------------------------------------------------------------
    # Key Builders
    # ------------------------------------------------------------------

    def _build_memo_key(self, payload: dict, prefix: str = 'memo') -> str:
        """
        Build a conversation-scoped cache key.

        Args:
            payload: Dict, the format is {
                "user_uid": user id,
                "conversation_uid": conversation id,
            }
            prefix: Cache namespace prefix.

        Return:
            str, the format is
            "{prefix}:{user_uid}:{conversation_uid}".

        Raises:
            KeyError: If user_uid or conversation_uid is missing.
        """
        user_uid = payload.get("user_uid")
        conversation_uid = payload.get("conversation_uid")

        if not all([user_uid, conversation_uid]):
            raise KeyError("user_uid and conversation_uid required")

        return f"{prefix}:{user_uid}:{conversation_uid}"

    def _build_resource_key(self, payload: dict) -> str:
        """
        Build a cache key for one read-through resource entry.

        Args:
            payload: Dict, the format is {
                "cache_group": resource cache namespace,
                "cache_key": resource identifier,
            }

        Return:
            str, the format is
            "resource:{quoted_cache_group}:{quoted_cache_key}".

        Raises:
            KeyError: If cache_group or cache_key is not a non-empty string.
        """
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
        """
        Build the cache-key prefix for a read-through resource group.

        Args:
            payload: Dict, the format is {
                "cache_group": resource cache namespace,
            }

        Return:
            str, the format is "resource:{quoted_cache_group}:".

        Raises:
            KeyError: If cache_group is not a non-empty string.
        """
        cache_group = payload.get("cache_group")
        if not isinstance(cache_group, str) or not cache_group:
            raise KeyError("non-empty cache_group required")
        return f"resource:{quote(cache_group, safe='')}:"

    # ------------------------------------------------------------------
    # Memo Redis (Conversation Cache)
    # ------------------------------------------------------------------

    @abstractmethod
    async def append_message(self, payload: dict) -> dict:
        """
        Append a message only when the conversation cache already exists.

        Args:
            payload: Dict, the format is {
                "user_uid": user id,
                "conversation_uid": conversation id,
                "message": {
                    "message_uid": unique message id,
                    "generation_id": str,
                    "role": 'user', 'ai', 'system', 'tool', 'info',
                    "name": "assistant / user / tool name",
                    "content": "message content",
                    "metadata": {...},
                    "extensions": {...},
                    "node_id": str,
                    "parent_id": str,
                    "msg_cursor": int,
                    "timestamp": str,
                    "is_deleted": bool,
                }
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or "success",
            }
        """
        pass
        
    @abstractmethod
    async def backfill_messages(self, payload: dict) -> dict:
        """
        Replace the cached conversation messages with a complete message list.

        Args:
            payload: Dict, the format is {
                "user_uid": user id,
                "conversation_uid": conversation id,
                "messages": [
                    {...},
                    ...
                ],
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or "success",
            }
        """
        pass
        
    @abstractmethod
    async def get_recent_messages(self, payload: dict) -> dict:
        """
        Get all messages in a conversation cache.

        Args:
            payload: Dict, the format is {
                "user_uid": user id,
                "conversation_uid": conversation id,
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or list[dict],
                "cache_hit": bool,
            }
        """
        pass
        
    @abstractmethod
    async def cache_current_messages_branch_chain(self, payload: dict) -> dict:
        """
        Cache the node id chain of the current conversation branch.

        Args:
            payload: Dict, the format is {
                "user_uid": user id,
                "conversation_uid": conversation id,
                "node_id_chain": list[str],
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or "success",
            }
        """
        pass
        
    @abstractmethod
    async def update_current_messages_branch_chain_cache(self, payload: dict) -> dict:
        """
        Update the cached branch chain from an existing parent node.

        If parent_id exists in the cached chain, nodes after that parent are
        replaced by node_id. A cache miss or unknown parent is a successful
        no-op.

        Args:
            payload: Dict, the format is {
                "user_uid": user id,
                "conversation_uid": conversation id,
                "node_id": new branch tip node id,
                "parent_id": parent node id,
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or "success" or no-op reason,
            }
        """
        pass
        
    @abstractmethod
    async def get_current_messages_branch_chain(self, payload: dict) -> dict:
        """
        Get the cached node id chain of the current conversation branch.

        Args:
            payload: Dict, the format is {
                "user_uid": user id,
                "conversation_uid": conversation id,
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or list[str],
                "cache_hit": bool,
            }
        """
        pass

    # ------------------------------------------------------------------
    # Read-through Resource Cache
    # ------------------------------------------------------------------

    @abstractmethod
    async def backfill_resource(self, payload: dict) -> dict:
        """
        Cache a successful data-store result.

        Args:
            payload: Dict, the format is {
                "cache_group": resource cache namespace,
                "cache_key": resource identifier,
                "messages": list[dict],
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or "success",
            }
        """
        pass

    @abstractmethod
    async def get_resource(self, payload: dict) -> dict:
        """
        Get a cached read-through resource result.

        Args:
            payload: Dict, the format is {
                "cache_group": resource cache namespace,
                "cache_key": resource identifier,
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or list[dict],
                "cache_hit": bool,
            }
        """
        pass

    @abstractmethod
    async def invalidate_resource(self, payload: dict) -> dict:
        """
        Invalidate one resource entry or every entry in a cache group.

        Args:
            payload: Dict, the format is {
                "cache_group": resource cache namespace,
                "cache_key": optional resource identifier,
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or "success",
            }
        """
        pass

    # ------------------------------------------------------------------
    # TTL
    # ------------------------------------------------------------------

    @abstractmethod
    async def set_expire(self, payload: dict, ttl_seconds: int = HOT_CACHE_DEFAULT_EXPIRE_SECONDS) -> dict:
        """
        Set the expiration time for a conversation message cache.

        Args:
            payload: Dict, the format is {
                "user_uid": user id,
                "conversation_uid": conversation id,
            }
            ttl_seconds: Number of seconds until the cache expires.

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or "success",
            }
        """
        pass

    @abstractmethod
    async def expire_immediately(self, payload: dict) -> dict:
        """
        Delete a conversation message cache immediately.

        Args:
            payload: Dict, the format is {
                "user_uid": user id,
                "conversation_uid": conversation id,
            }

        Return:
            dict, the format is {
                "success": bool,
                "messages": "fail: {e}" or "success",
            }
        """
        pass
