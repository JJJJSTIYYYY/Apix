import asyncio
import copy
import json
import os
import time
from pathlib import Path
from typing import Any, Optional

from apix.agent.store.core.server.cache_store.cache_server_base import CacheServerBase
from apix.agent.store.core.server.cache_store.utils import cache_store_handler
from apix.common.lifespan.auto_init import auto_init
from apix.common.utils.logger import logger
from apix.config.base_config import BASE_DIR, HOT_CACHE_DEFAULT_EXPIRE_SECONDS, STATIC_CACHE_DEFAULT_EXPIRE_SECONDS


class BuiltinService(CacheServerBase):
    """A TTL-aware cache that preserves canonical message dictionaries."""

    def __init__(self, persistence_path: Optional[str | Path] = None):
        self._persistence_path = Path(
            persistence_path
            or (Path(BASE_DIR) / "builtin_cache_store.json").expanduser().resolve()
        )
        self._cache: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()


    async def start(self) -> None:
        """Restore valid entries saved by the most recent graceful shutdown."""
        async with self._lock:
            self._cache.clear()
            if not self._persistence_path.exists():
                return

            try:
                with self._persistence_path.open("r", encoding="utf-8") as file:
                    stored_cache = json.load(file)
                if not isinstance(stored_cache, dict):
                    raise ValueError("cache persistence content must be an object")

                now = time.time()
                self._cache = {
                    key: item
                    for key, item in stored_cache.items()
                    if self._is_valid_item(item, now)
                }
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
                logger.warning(f"Unable to restore builtin cache: {error}")
                self._cache.clear()


    async def stop(self) -> None:
        """Persist valid entries atomically for restoration on the next start."""
        async with self._lock:
            self._purge_expired()
            self._persistence_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = self._persistence_path.with_suffix(
                f"{self._persistence_path.suffix}.tmp"
            )
            try:
                with temporary_path.open("w", encoding="utf-8") as file:
                    json.dump(self._cache, file, ensure_ascii=False, separators=(",", ":"))
                os.replace(temporary_path, self._persistence_path)
            except (OSError, TypeError, ValueError) as error:
                logger.exception(f"Unable to persist builtin cache: {error}")
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass
                raise


    @cache_store_handler
    async def append_message(self, payload: dict) -> dict:
        key = self._build_memo_key(payload)
        message = payload.get("message", {})
        async with self._lock:
            item = self._get_item(key)
            if item is None:
                logger.warning("Builtin cache key not exists.")
                return {"success": True, "messages": "success"}
            item["value"].append(copy.deepcopy(message))
            item["expires_at"] = time.time() + HOT_CACHE_DEFAULT_EXPIRE_SECONDS
        return {"success": True, "messages": "success"}

    @cache_store_handler
    async def backfill_messages(self, payload: dict) -> dict:
        key = self._build_memo_key(payload)
        messages = payload.get("messages", [])
        if not isinstance(messages, list):
            raise ValueError("Messages must be a list")
        async with self._lock:
            # Redis leaves no key when an empty list is backfilled.
            if messages:
                self._set_item(
                    key,
                    copy.deepcopy(messages),
                    HOT_CACHE_DEFAULT_EXPIRE_SECONDS,
                )
            else:
                self._cache.pop(key, None)
        return {"success": True, "messages": "success"}

    @cache_store_handler
    async def get_recent_messages(self, payload: dict) -> dict:
        key = self._build_memo_key(payload)
        async with self._lock:
            item = self._get_item(key)
            if item is None or not item["value"]:
                return {"success": True, "messages": [], "cache_hit": False}
            return {
                "success": True,
                "messages": copy.deepcopy(item["value"]),
                "cache_hit": True,
            }

    @cache_store_handler
    async def cache_current_messages_branch_chain(self, payload: dict) -> dict:
        node_id_chain = payload.get("node_id_chain", [])
        if not isinstance(node_id_chain, list):
            raise ValueError("node_id_chain must be a list")
        key = self._build_memo_key(payload, prefix="chain")
        async with self._lock:
            self._set_item(
                key,
                copy.deepcopy(node_id_chain),
                STATIC_CACHE_DEFAULT_EXPIRE_SECONDS,
            )
        return {"success": True, "messages": "success"}

    @cache_store_handler
    async def update_current_messages_branch_chain_cache(self, payload: dict) -> dict:
        node_id = payload["node_id"]
        parent_id = payload["parent_id"]
        key = self._build_memo_key(payload, prefix="chain")
        async with self._lock:
            item = self._get_item(key)
            if item is None:
                return {"success": True, "messages": "cache not found"}
            node_id_chain = item["value"]
            if not isinstance(node_id_chain, list):
                raise ValueError("Cached node_id_chain must be a list")
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
                return {"success": True, "messages": "already up to date"}
            self._set_item(
                key,
                node_id_chain[: parent_index + 1] + [node_id],
                STATIC_CACHE_DEFAULT_EXPIRE_SECONDS,
            )
        return {"success": True, "messages": "success"}

    @cache_store_handler
    async def get_current_messages_branch_chain(self, payload: dict) -> dict:
        key = self._build_memo_key(payload, prefix="chain")
        async with self._lock:
            item = self._get_item(key)
            if item is None:
                return {"success": True, "messages": [], "cache_hit": False}
            return {
                "success": True,
                "messages": copy.deepcopy(item["value"]),
                "cache_hit": True,
            }

    @cache_store_handler
    async def set_expire(
        self, payload: dict, ttl_seconds: int = HOT_CACHE_DEFAULT_EXPIRE_SECONDS
    ) -> dict:
        key = self._build_memo_key(payload)
        async with self._lock:
            item = self._get_item(key)
            if item is not None:
                item["expires_at"] = time.time() + ttl_seconds
        return {"success": True, "messages": "success"}

    @cache_store_handler
    async def expire_immediately(self, payload: dict) -> dict:
        key = self._build_memo_key(payload)
        async with self._lock:
            self._cache.pop(key, None)
        return {"success": True, "messages": "success"}

    # ------------------------------------------------------------------
    # Read-through Resource Cache
    # ------------------------------------------------------------------

    @cache_store_handler
    async def backfill_resource(self, payload: dict) -> dict:
        messages = payload.get("messages")
        if not isinstance(messages, list):
            raise ValueError("Resource messages must be a list")
        key = self._build_resource_key(payload)
        async with self._lock:
            self._set_item(
                key,
                copy.deepcopy(messages),
                STATIC_CACHE_DEFAULT_EXPIRE_SECONDS,
            )
        return {"success": True, "messages": "success"}

    @cache_store_handler
    async def get_resource(self, payload: dict) -> dict:
        key = self._build_resource_key(payload)
        async with self._lock:
            item = self._get_item(key)
            if item is None:
                return {
                    "success": True,
                    "messages": [],
                    "cache_hit": False,
                }
            return {
                "success": True,
                "messages": copy.deepcopy(item["value"]),
                "cache_hit": True,
            }

    @cache_store_handler
    async def invalidate_resource(self, payload: dict) -> dict:
        async with self._lock:
            if payload.get("cache_key") is not None:
                self._cache.pop(self._build_resource_key(payload), None)
            else:
                prefix = self._build_resource_prefix(payload)
                matching_keys = [
                    key for key in self._cache if key.startswith(prefix)
                ]
                for key in matching_keys:
                    self._cache.pop(key, None)
        return {"success": True, "messages": "success"}

        
    def _set_item(self, key: str, value: Any, ttl_seconds: int) -> None:
        self._cache[key] = {"value": value, "expires_at": time.time() + ttl_seconds}


    def _get_item(self, key: str) -> Optional[dict[str, Any]]:
        item = self._cache.get(key)
        if item is None:
            return None
        if not self._is_valid_item(item, time.time()):
            self._cache.pop(key, None)
            return None
        return item
    

    def _purge_expired(self) -> None:
        now = time.time()
        self._cache = {
            key: item for key, item in self._cache.items() if self._is_valid_item(item, now)
        }


    @staticmethod
    def _is_valid_item(item: Any, now: float) -> bool:
        return (
            isinstance(item, dict)
            and "value" in item
            and isinstance(item.get("expires_at"), (int, float))
            and item["expires_at"] > now
        )


cache_server = BuiltinService()
auto_init.register(cache_server)
