import asyncio
import uuid
from typing import Dict, List, Optional

from apix_agent.commons.type_def import AgentConfigSchema
from apix_agent.apix_agent_core.tools.web_search.models import ImageResultItem, UrlResultItem, ContentResultItem
from apix_agent.apix_agent_core.tools.web_search.providers.base import BaseSearchProvider
from apix_agent.apix_agent_core.tools.web_search.providers import PROVIDER_REGISTRY
from apix_agent.apix_agent_core.tools.web_search.cleaner import SearchResultCleaner
from apix_agent.apix_agent_core.tools.web_search.router import SearchProviderRouter, search_engine_router as router


class WebSearchManager:
    """
    Global singleton manager for web search.
    Designed for Graph Agent usage.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        # search_id -> asyncio.Task
        self._tasks: Dict[str, asyncio.Task] = {}

        # Stateless cleaner
        self._cleaner = SearchResultCleaner()

    # ============================================================
    # Tool 1: keyword -> UrlResultItem[]
    # ============================================================
    async def submit_link_search(
        self,
        keyword: str | List[str],
        config: Optional[AgentConfigSchema] = None,
    ) -> tuple[str, str]:
        """
        Submit keyword-based link search.
        Provider selection is delegated to router.
        """
        if isinstance(keyword, list):
            keyword = " ".join(keyword)

        config = config or {}

        # Router is async
        provider_name = await router.choose_link_provider(config)

        provider_cls = PROVIDER_REGISTRY.get(provider_name)
        if not provider_cls:
            raise RuntimeError(f"Provider not registered: {provider_name}")

        provider = provider_cls(
            api_key=config.get("link_api_key") or None
        )

        search_id = str(uuid.uuid4())

        task = asyncio.create_task(
            self._run_link_search(
                provider=provider,
                keyword=keyword,
                config=config,
            )
        )

        self._tasks[search_id] = task
        return provider.name, search_id

    async def _run_link_search(
        self,
        provider: BaseSearchProvider,
        keyword: str,
        config: AgentConfigSchema,
    ) -> tuple[List[UrlResultItem], List[ImageResultItem]]:

        raw_results = await provider.search_links(keyword)

        if isinstance(raw_results, tuple):
            url_results, image_results = raw_results
        else:
            url_results = raw_results
            image_results = []

        return self._cleaner.clean_links(url_results), image_results

    # ============================================================
    # Tool 2: url(s) -> ContentResultItem[]
    # ============================================================
    async def submit_content_fetch(
        self,
        urls: str | List[str],
        config: Optional[AgentConfigSchema] = None,
    ) -> tuple[str, str]:
        """
        Submit content fetching task.
        """
        if isinstance(urls, str):
            urls = [urls]

        config = config or {}

        provider_name = await router.choose_content_provider(config)

        provider_cls = PROVIDER_REGISTRY.get(provider_name)
        if not provider_cls:
            raise RuntimeError(f"Provider not registered: {provider_name}")

        provider = provider_cls(
            api_key=config.get("content_api_key") or None
        )

        search_id = str(uuid.uuid4())

        task = asyncio.create_task(
            self._run_content_fetch(
                provider=provider,
                urls=urls,
                config=config,
            )
        )

        self._tasks[search_id] = task
        return provider.name, search_id

    async def _run_content_fetch(
        self,
        provider: BaseSearchProvider,
        urls: List[str],
        config: AgentConfigSchema,
    ) -> List[ContentResultItem]:

        results: List[ContentResultItem] = []
        for url in urls:
            item = await provider.fetch_content(url)
            results.append(
                await self._cleaner.clean_content(item, config)
            )

        return results

    # ============================================================
    # Result handling
    # ============================================================
    async def wait_result(self, search_id: str):
        task = self._tasks.get(search_id)
        if not task:
            raise KeyError(f"Search task not found: {search_id}")

        try:
            return await task
        finally:
            self._tasks.pop(search_id, None)


    def get_search_providers(self) -> List[str]:
        return list(PROVIDER_REGISTRY.keys())


# Singleton instance
manager = WebSearchManager()
