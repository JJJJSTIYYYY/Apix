import asyncio
import hashlib
import json
import time
from typing import Dict, List, Type, Optional

from apix_agent.commons.type_def import AgentConfigSchema
from apix_agent.apix_agent_core.tools.web_search.providers.base import BaseSearchProvider
from apix_agent.apix_agent_core.tools.web_search.providers import PROVIDER_REGISTRY


class SearchProviderRouter:
    """
    Intelligent provider router.

    Router does NOT guess availability.
    Router verifies availability.
    """

    def __init__(self):
        # key: hash(config + task_type)
        # value: provider name
        self.router_cache: Dict[str, str] = {}

        # key: task_type ("link" / "content")
        # value: ttl seconds (0 or None means no expiry)
        self.router_cache_ttl: Dict[str, Optional[int]] = {
            "link": None,
            "content": None,
        }

        # key: cache_key
        # value: expire timestamp
        self._cache_expire_at: Dict[str, float] = {}

    # ============================================================
    # Cache helpers
    # ============================================================
    def _hash_cache_key(self, *, task_type: str, config: AgentConfigSchema) -> str:
        """
        Build cache key according to task_type.
        """
        if task_type == "link":
            payload = {
                "task_type": "link",
                "provider": config.get("link_provider") or "",
                "api_key": config.get("link_api_key") or "",
            }
        elif task_type == "content":
            payload = {
                "task_type": "content",
                "provider": config.get("content_provider") or "",
                "api_key": config.get("content_api_key") or "",
            }
        else:
            raise ValueError(f"Unknown task_type: {task_type}")

        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _get_cached(self, cache_key: str) -> Optional[str]:
        if cache_key not in self.router_cache:
            return None

        expire_at = self._cache_expire_at.get(cache_key)
        if expire_at is not None and time.time() > expire_at:
            # cache expired
            self.router_cache.pop(cache_key, None)
            self._cache_expire_at.pop(cache_key, None)
            return None

        return self.router_cache[cache_key]

    def _set_cache(self, *, cache_key: str, value: str, task_type: str) -> None:
        self.router_cache[cache_key] = value

        ttl = self.router_cache_ttl.get(task_type)
        if ttl is not None and ttl > 0:
            self._cache_expire_at[cache_key] = time.time() + ttl
        else:
            self._cache_expire_at.pop(cache_key, None)

    # ============================================================
    # Public APIs
    # ============================================================
    async def choose_link_provider(self, config: AgentConfigSchema) -> str:
        return await self._choose_provider(
            config=config,
            task_type="link",
        )

    async def choose_content_provider(self, config: AgentConfigSchema) -> str:
        return await self._choose_provider(
            config=config,
            task_type="content",
        )

    # ============================================================
    # Core decision logic
    # ============================================================
    async def _choose_provider(
        self,
        *,
        config: AgentConfigSchema,
        task_type: str,
    ) -> str:
        """
        Apply the 4-rule matrix.
        Cache is checked BEFORE routing.
        """
        cache_key = self._hash_cache_key(
            task_type=task_type,
            config=config,
        )

        # -------- cache first --------
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        # extract effective config
        if task_type == "link":
            explicit_provider = config.get("link_provider") or ""
            api_key = config.get("link_api_key") or ""
        else:
            explicit_provider = config.get("content_provider") or ""
            api_key = config.get("content_api_key") or ""

        # -------- case 1 / 4: provider explicitly given --------
        if explicit_provider:
            provider_cls = self._get_provider_cls(explicit_provider)

            if provider_cls.requires_api_key and not api_key:
                chosen = await self._pick_no_key_provider(task_type)
            else:
                chosen = explicit_provider

            self._set_cache(
                cache_key=cache_key,
                value=chosen,
                task_type=task_type,
            )
            return chosen

        # -------- case 2: only api_key provided → auto routing --------
        if api_key:
            chosen = await self._auto_route_with_api_key(api_key, task_type)
            self._set_cache(
                cache_key=cache_key,
                value=chosen,
                task_type=task_type,
            )
            return chosen

        # -------- case 3: neither provided → no-key provider --------
        chosen = await self._pick_no_key_provider(task_type)
        self._set_cache(
            cache_key=cache_key,
            value=chosen,
            task_type=task_type,
        )
        return chosen

    # ============================================================
    # Auto routing
    # ============================================================
    async def _auto_route_with_api_key(self, api_key: str, task_type: str) -> str:
        """
        Concurrently probe all providers that:
        - support task_type
        - require api_key

        Return the FIRST provider that successfully passes probe().
        """
        candidates = self._providers_for_task(task_type, require_key=True)

        if not candidates:
            return await self._pick_no_key_provider(task_type)

        # Create tasks lazily so that we can cancel losers early
        tasks: List[asyncio.Task] = []
        for name in candidates:
            task = asyncio.create_task(
                self._probe_provider(name=name, api_key=api_key)
            )
            tasks.append(task)

        try:
            # Iterate in completion order (fastest first)
            for finished in asyncio.as_completed(tasks):
                result = await finished
                if result:
                    # First successful provider wins
                    return result
        finally:
            # Cancel all pending tasks to avoid wasting resources
            for task in tasks:
                if not task.done():
                    task.cancel()

        # No provider passed probe
        return await self._pick_no_key_provider(task_type)

    async def _probe_provider(
        self,
        *,
        name: str,
        api_key: str,
    ) -> Optional[str]:
        """
        Probe a single provider.

        Return provider name if probe succeeds, otherwise None.
        """
        try:
            provider_cls = PROVIDER_REGISTRY[name]
            provider = provider_cls(api_key=api_key)

            ok = await provider.probe()
            return name if ok else None

        except PermissionError:
            # Invalid or unauthorized api_key
            return None

        except asyncio.CancelledError:
            # Task was cancelled because another provider won
            raise

    # ============================================================
    # Fallback
    # ============================================================
    async def _pick_no_key_provider(self, task_type: str) -> str:
        """
        Concurrently probe all providers that do NOT require api_key.

        Return the FIRST provider that successfully passes probe().
        """
        candidates = self._providers_for_task(task_type, require_key=False)

        if not candidates:
            raise RuntimeError("No provider without api_key is available")

        tasks: List[asyncio.Task] = []
        for name in candidates:
            task = asyncio.create_task(
                self._probe_no_key_provider(name=name)
            )
            tasks.append(task)

        try:
            for finished in asyncio.as_completed(tasks):
                result = await finished
                if result:
                    return result
        finally:
            # Cancel all pending tasks once a winner is found
            for task in tasks:
                if not task.done():
                    task.cancel()

        raise RuntimeError("No provider without api_key is available")

    async def _probe_no_key_provider(
        self,
        *,
        name: str,
    ) -> Optional[str]:
        """
        Probe a provider that does not require api_key.
        """
        try:
            provider_cls = PROVIDER_REGISTRY[name]
            provider = provider_cls()

            ok = await provider.probe()
            return name if ok else None

        except asyncio.CancelledError:
            # Task cancelled because another provider won the race
            raise

        except Exception:
            # Any error means this provider is not usable
            return None

    # ============================================================
    # Provider registry helpers
    # ============================================================
    def _providers_for_task(
        self,
        task_type: str,
        *,
        require_key: bool,
    ) -> List[str]:
        result = []

        for name, cls in PROVIDER_REGISTRY.items():
            if cls.supports_task(task_type) and cls.requires_api_key == require_key:
                result.append(name)

        return result

    @staticmethod
    def _get_provider_cls(name: str) -> Type[BaseSearchProvider]:
        if name not in PROVIDER_REGISTRY:
            raise ValueError(f"Unknown provider: {name}")
        return PROVIDER_REGISTRY[name]



search_engine_router = SearchProviderRouter()