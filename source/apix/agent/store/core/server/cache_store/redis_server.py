import json

import redis.asyncio as redis

from apix.agent.store.core.server.cache_store.cache_server_base import CacheServerBase
from apix.common.lifespan.auto_init import auto_init
from apix.common.utils.logger import logger
from apix.config.base_config import MEMO_REDIS_URL, REDIS_POOL_SIZE, HOT_CACHE_DEFAULT_EXPIRE_SECONDS, STATIC_CACHE_DEFAULT_EXPIRE_SECONDS


class RedisService(CacheServerBase):
    """
    Redis is NOT the source of truth.
    """

    def __init__(
        self,
        memo_redis_url: str = MEMO_REDIS_URL,
    ):
        self._memo_redis = redis.from_url(
            memo_redis_url,
            decode_responses=True,
            max_connections=REDIS_POOL_SIZE,
            socket_keepalive=True,
        )

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        await self._memo_redis.aclose()

    # ------------------------------------------------------------------
    # Memo Redis (Conversation Cache)
    # ------------------------------------------------------------------

    async def append_message(self, payload: dict) -> dict:
        """
        Append message ONLY IF redis key already exists.
        This method should only be called after append message to MySQL and then backfilling Redis.

        Args:
            payload: Dict, the format is {
                "user_uid": user id,
                "conversation_uid": conversation id,
                "message": {
                    "message_uid": "application unique message id",
                    "role": 'user', 'ai', 'system', 'tool', 'info'
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
                "success": True / False,
                "messages": "success / fail: {e}",
            }
        """
        logger.trace()
        try:
            key = self._build_memo_key(payload)

            # Redis miss → skip silently
            if not await self._memo_redis.exists(key):
                logger.warning(
                    "Redis key not exists."
                )
                return {
                    "success": True,
                    "messages": "success",
                }

            message = payload.get("message", {})

            async with self._memo_redis.pipeline() as pipe:
                pipe.rpush(key, json.dumps(message, ensure_ascii=False))

                pipe.expire(key, HOT_CACHE_DEFAULT_EXPIRE_SECONDS)
                await pipe.execute()

            return {
                "success": True,
                "messages": "success",
            }

        except Exception as e:
            logger.exception(f"Error: {type(e).__name__}: {e}")
            return {
                "success": False, 
                "messages": f"fail: {e}"
            }
        
    async def backfill_messages(self, payload: dict) -> dict:
        """
        Backfill FULL messages into Redis (overwrite mode).

        This method should only be called after fetching FULL messages from MySQL.

        Args:
            payload: Dict, the format is {
                "user_uid": user id,
                "conversation_uid": conversation id,
                "messages": [ ... ]  # FULL message list
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "success / fail: {e}",
            }
        """
        logger.trace()
        try:
            key = self._build_memo_key(payload)
            messages = payload.get("messages", [])

            if not isinstance(messages, list):
                raise ValueError("Messages must be a list")

            # Empty list is allowed → clear cache
            async with self._memo_redis.pipeline() as pipe:
                # ---- Overwrite instead of append ----
                pipe.delete(key)

                if messages:
                    pipe.rpush(
                        key,
                        *[json.dumps(msg, ensure_ascii=False) for msg in messages]
                    )

                pipe.expire(key, HOT_CACHE_DEFAULT_EXPIRE_SECONDS)
                await pipe.execute()

            return {
                "success": True,
                "messages": "success",
            }

        except Exception as e:
            logger.exception(f"Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}"
            }
        
    async def get_recent_messages(self, payload: dict) -> dict:
        """
        Fetch FULL messages from Redis cache (no cursor).

        Redis miss should be handled by caller (fallback to MySQL and backfill).

        Args:
            payload: Dict, the format is {
                "user_uid": user id,
                "conversation_uid": conversation id,
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or [...] (list of message dicts),
                "cache_hit": bool
            }
        """
        logger.trace()
        try:
            key = self._build_memo_key(payload)

            # ---- Fetch FULL list from Redis ----
            raw = await self._memo_redis.lrange(key, 0, -1)
            if not raw:
                # Redis miss: empty or expired
                return {
                    "success": True,
                    "messages": [],
                    "cache_hit": False,
                }

            # ---- Decode all messages ----
            messages = [json.loads(m) for m in raw]

            return {
                "success": True,
                "messages": messages,
                "cache_hit": True,
            }

        except Exception as e:
            logger.exception(f"Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    async def cache_current_messages_branch_chain(self, payload: dict) -> dict:
        """
        Cache the node id chain of the user's current message branch.

        The chain contains all node ids from the root node to the current
        branch tip node, preserving the exact branch path selected by the user.

        Args:
            payload: Dict, the format is {
                "user_uid": user id,
                "conversation_uid": conversation id,
                "node_id_chain": list
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "success / fail: {e}",
            }
        """
        logger.trace()
        try:
            node_id_chain = payload.get("node_id_chain", [])

            if not isinstance(node_id_chain, list):
                raise ValueError("node_id_chain must be a list")

            key = self._build_memo_key(payload, prefix='chain')

            await self._memo_redis.set(
                key,
                json.dumps(node_id_chain, ensure_ascii=False),
                ex=STATIC_CACHE_DEFAULT_EXPIRE_SECONDS,
            )

            return {
                "success": True,
                "messages": "success",
            }

        except Exception as e:
            logger.exception(
                f"Error: {type(e).__name__}: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    async def update_current_messages_branch_chain_cache(self, payload: dict) -> dict:
        """
        Best effort to update the cached chain.

        If parent_id exist in cached chain, update node_id to cache,
        otherwise do nothing.

        Args:
            payload: Dict, the format is {
                "user_uid": user id,
                "conversation_uid": conversation id,
                "node_id": str,
                "parent_id": str,
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "success / fail: {e}",
            }
        """
        logger.trace()
        try:
            node_id = payload["node_id"]
            parent_id = payload["parent_id"]

            key = self._build_memo_key(payload, prefix="chain")

            cached_chain = await self._memo_redis.get(key)

            # Cache miss, do nothing
            if not cached_chain:
                return {
                    "success": True,
                    "messages": "cache not found",
                }

            node_id_chain = json.loads(cached_chain)

            if not isinstance(node_id_chain, list):
                raise ValueError("Cached node_id_chain must be a list")

            # Parent node not in current branch chain, do nothing
            if parent_id not in node_id_chain:
                return {
                    "success": True,
                    "messages": "parent_id not found in cache",
                }

            parent_index = node_id_chain.index(parent_id)
            
            if (
                parent_index == len(node_id_chain) - 2
                and node_id_chain[-1] == node_id
            ):
                return {
                    "success": True,
                    "messages": "already up to date",
                }

            # Keep nodes before and including parent_id, then append new node_id as branch tip.
            new_chain = node_id_chain[: parent_index + 1]
            new_chain.append(node_id)

            await self._memo_redis.set(
                key,
                json.dumps(new_chain, ensure_ascii=False),
                ex=STATIC_CACHE_DEFAULT_EXPIRE_SECONDS,
            )

            return {
                "success": True,
                "messages": "success",
            }

        except Exception as e:
            logger.exception(
                f"Error: {type(e).__name__}: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }
        
    async def get_current_messages_branch_chain(self, payload: dict) -> dict:
        """
        Fetch the cached node id chain of the user's current message branch.

        Args:
            payload: Dict, the format is {
                "user_uid": user id,
                "conversation_uid": conversation id
            }

        Return:
            dict, the format is {
                "success": True / False,
                "messages": "fail: {e}" or list,
                "cache_hit": bool
            }
        """
        logger.trace()
        try:
            key = self._build_memo_key(payload, prefix='chain')

            raw = await self._memo_redis.get(key)

            if not raw:
                return {
                    "success": True,
                    "messages": [],
                    "cache_hit": False,
                }

            node_id_chain = json.loads(raw)

            return {
                "success": True,
                "messages": node_id_chain,
                "cache_hit": True,
            }

        except Exception as e:
            logger.exception(
                f"Error: {type(e).__name__}: {e}"
            )
            return {
                "success": False,
                "messages": f"fail: {e}",
            }

    # ------------------------------------------------------------------
    # Read-through Resource Cache
    # ------------------------------------------------------------------

    async def backfill_resource(self, payload: dict) -> dict:
        logger.trace()
        try:
            messages = payload.get("messages")
            if not isinstance(messages, list):
                raise ValueError("Resource messages must be a list")
            await self._memo_redis.set(
                self._build_resource_key(payload),
                json.dumps(messages, ensure_ascii=False),
                ex=STATIC_CACHE_DEFAULT_EXPIRE_SECONDS,
            )
            return {"success": True, "messages": "success"}
        except Exception as e:
            logger.exception(f"Error: {type(e).__name__}: {e}")
            return {"success": False, "messages": f"fail: {e}"}


    async def get_resource(self, payload: dict) -> dict:
        logger.trace()
        try:
            raw = await self._memo_redis.get(
                self._build_resource_key(payload)
            )
            if raw is None:
                return {
                    "success": True,
                    "messages": [],
                    "cache_hit": False,
                }
            messages = json.loads(raw)
            if not isinstance(messages, list):
                raise ValueError("Cached resource messages must be a list")
            return {
                "success": True,
                "messages": messages,
                "cache_hit": True,
            }
        except Exception as e:
            logger.exception(f"Error: {type(e).__name__}: {e}")
            return {"success": False, "messages": f"fail: {e}"}


    async def invalidate_resource(self, payload: dict) -> dict:
        logger.trace()
        try:
            if payload.get("cache_key") is not None:
                keys = [self._build_resource_key(payload)]
            else:
                keys = [
                    key
                    async for key in self._memo_redis.scan_iter(
                        match=f"{self._build_resource_prefix(payload)}*"
                    )
                ]
            if keys:
                await self._memo_redis.delete(*keys)
            return {"success": True, "messages": "success"}
        except Exception as e:
            logger.exception(f"Error: {type(e).__name__}: {e}")
            return {"success": False, "messages": f"fail: {e}"}


    # ------------------------------------------------------------------
    # TTL
    # ------------------------------------------------------------------

    async def set_expire(self, payload: dict, ttl_seconds: int = HOT_CACHE_DEFAULT_EXPIRE_SECONDS) -> dict:
        """
        set_expire to given ttl_seconds.
        In order to unified:
        - When payload dictionary contains key 'task_hash', it will be seen as set tasks TTL in redis.
        - Else set conversation message list's TTL.
        """
        logger.trace()
        try:
            await self._memo_redis.expire(
                self._build_memo_key(payload), ttl_seconds
            )
        except Exception as e:
            logger.exception(f"Error: {type(e).__name__}: {e}")
            return {"success": False, "messages": f"fail: {e}"}
        return {
                "success": True,
                "messages": "success",
            }

    async def expire_immediately(self, payload: dict) -> dict:
        """
        Expire key immediately.

        Unified behavior:
        - When payload contains 'task_hash', fetch task info then delete task redis key.
        - Else delete memo redis key.
        """
        logger.trace()
        try:
            await self._memo_redis.delete(
                self._build_memo_key(payload)
            )

            return {
                "success": True,
                "messages": "success",
            }

        except Exception as e:
            logger.exception(f"Error: {type(e).__name__}: {e}")
            return {
                "success": False,
                "messages": f"fail: {e}",
            }


cache_server = RedisService(MEMO_REDIS_URL)
auto_init.register(cache_server)
