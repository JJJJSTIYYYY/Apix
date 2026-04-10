import asyncio
from typing import List

from tavily import TavilyClient

from apix_agent.apix_agent_core.tools.web_search.models import (
    ImageResultItem,
    UrlResultItem,
    ContentResultItem,
)
from apix_agent.apix_agent_core.tools.web_search.providers.base import BaseSearchProvider
from apix_agent.commons.logger import logger


class TavilyProvider(BaseSearchProvider):
    """
    Tavily search provider.

    Supports:
    - keyword -> urls
    - url -> content
    """

    name = "Tavily"
    requires_api_key = True
    supports_link_search = True
    supports_content_fetch = True

    # --------------------------------------------------
    # internal client
    # --------------------------------------------------
    def _client(self) -> TavilyClient:
        """
        Create Tavily client.

        Raise RuntimeError if api_key is missing.
        """
        if not self.api_key:
            raise RuntimeError("Tavily API key is required")

        return TavilyClient(api_key=self.api_key)

    # --------------------------------------------------
    # keyword -> urls
    # --------------------------------------------------
    async def search_links(self, keyword: str) -> tuple[List[UrlResultItem], List[ImageResultItem]]:
        """
        Search URLs using Tavily.

        Tavily SDK is synchronous, so this method delegates
        the actual work to a background thread.
        """
        return await asyncio.to_thread(self._search_links_sync, keyword)

    def _search_links_sync(self, keyword: str) -> tuple[List[UrlResultItem], List[ImageResultItem]]:
        """
        Synchronous implementation of Tavily link search.
        """
        client = self._client()

        response = client.search(
            query=keyword,
            max_results=10,
            include_raw_content=False,
            include_images=True,
        )

        results: List[UrlResultItem] = []
        images: List[ImageResultItem] = []

        for item in response.get("results", []):
            url = item.get("url")
            if not url:
                continue

            results.append(
                UrlResultItem(
                    title=item.get("title", "Untitled link"),
                    url=url,
                    source="tavily",
                    describe=item.get("content", ""),
                )
            )

        for index, image_url in enumerate(response.get("images", []), start=1):
            if not image_url:
                continue

            images.append(
                ImageResultItem(
                    name=f"Image {index}",
                    url=image_url,
                    source="tavily",
                    host_page_url=None,
                )
            )

        return results, images

    # --------------------------------------------------
    # url -> content
    # --------------------------------------------------
    async def fetch_content(self, url: str) -> ContentResultItem:
        """
        Fetch page content using Tavily.

        This method is async but internally runs the
        synchronous Tavily SDK in a worker thread.
        """
        return await asyncio.to_thread(self._fetch_content_sync, url)

    def _fetch_content_sync(self, url: str) -> ContentResultItem:
        """
        Synchronous implementation of Tavily content extraction.
        """
        client = self._client()

        response = client.extract(
            urls=[url],
            include_images=False,
            include_favicon=False,
            timeout=15,
        )

        results = response.get("results", [])
        if not results:
            raise RuntimeError(f"No content fetched for url: {url}")

        item = results[0]

        content = item.get("raw_content") or ""
        if not content:
            content = str(response.get("failed_results", ""))

        return ContentResultItem(
            title=item.get("title", "tavily content"),
            url=url,
            content=content,
            source="tavily",
            content_type="text",
        )

    # --------------------------------------------------
    # probe
    # --------------------------------------------------
    async def probe(self) -> bool:
        """
        Probe Tavily availability by performing a minimal search.

        Return True if provider is usable.
        Return False for auth failure or temporary unavailability.
        """
        try:
            await self.search_links("test")
            return True
        except Exception as e:
            logger.warning(f"[Tavily] Unavailable: {type(e)}: {e}")
            msg = str(e).lower()
            if "401" in msg or "403" in msg:
                return False
            return False