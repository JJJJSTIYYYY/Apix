import asyncio
from typing import List, Optional

from langchain_community.utilities import SearxSearchWrapper

from apix_agent.apix_agent_core.tools.web_search.models import UrlResultItem
from apix_agent.apix_agent_core.tools.web_search.providers.base import BaseSearchProvider
from apix_agent.commons.logger import logger


class SearxNGProvider(BaseSearchProvider):
    """
    SearxNG meta search engine provider (LangChain wrapper).

    Supports:
    - keyword -> urls
    """

    name = "SearXNG"
    requires_api_key = False
    supports_link_search = True
    supports_content_fetch = False

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "http://localhost:8080",
        engines: Optional[list[str]] = None,
    ):
        super().__init__(api_key=api_key)

        # LangChain Searx wrapper (synchronous)
        self.wrapper = SearxSearchWrapper(
            searx_host=base_url,
            engines=engines,
        )

        # Optional: some instances require Authorization header
        if api_key:
            self.wrapper.headers = {
                "Authorization": f"Bearer {api_key}"
            }

    # --------------------------------------------------
    # keyword -> urls
    # --------------------------------------------------
    async def search_links(self, keyword: str) -> List[UrlResultItem]:
        """
        Search URLs using SearxNG via LangChain wrapper.

        This method is async but internally uses a synchronous wrapper,
        so the blocking call is executed in a worker thread.
        """
        return await asyncio.to_thread(self._search_links_sync, keyword)

    def _search_links_sync(self, keyword: str) -> List[UrlResultItem]:
        """
        Synchronous implementation of SearxNG link search.
        """
        # results is a list of dicts with keys like: title, link, snippet
        results = self.wrapper.results(keyword, num_results=10)

        items: List[UrlResultItem] = []
        for item in results:
            url = item.get("link")
            if not url:
                continue

            items.append(
                UrlResultItem(
                    title=item.get("title", "Untitled link"),
                    url=url,
                    source="searxng",
                    describe=item.get("snippet", ""),
                )
            )

        return items

    # --------------------------------------------------
    # probe
    # --------------------------------------------------
    async def probe(self) -> bool:
        """
        Probe SearxNG availability by performing a minimal search.

        Return True if the instance is reachable and usable.
        Return False for network errors, misconfiguration, or auth failure.
        """
        try:
            await self.search_links("test")
            return True
        except Exception as e:
            logger.warning(f"[SearxNG] Unavailable: {type(e)}: {e}")
            return False

    def set_base_url(self, base_url: str) -> None:
        """
        Set the base URL of the SearxNG instance.
        """
        self.wrapper.searx_host = base_url

    def set_engines(self, engines: List[str]) -> None:
        """
        Set the search engines to use in SearxNG.
        """
        self.wrapper.engines = engines
