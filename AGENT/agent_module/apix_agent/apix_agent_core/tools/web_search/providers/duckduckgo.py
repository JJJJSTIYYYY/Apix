import asyncio
from typing import List
from ddgs import DDGS

from apix_agent.apix_agent_core.tools.web_search.models import ImageResultItem, UrlResultItem
from apix_agent.apix_agent_core.tools.web_search.providers.base import BaseSearchProvider
from apix_agent.commons.logger import logger


class DuckDuckGoProvider(BaseSearchProvider):
    """
    DuckDuckGo search provider.

    Supports:
    - keyword -> urls
    - keyword -> images

    Notes:
    - No API key required
    """

    name = "DuckDuckGo"
    requires_api_key = False
    supports_link_search = True
    supports_content_fetch = False

    async def search_links(self, keyword: str) -> tuple[List[UrlResultItem], List[ImageResultItem]]:
        """
        Search links and images using DuckDuckGo.

        This method is async but internally runs blocking code
        in a worker thread.
        """
        return await asyncio.to_thread(self._search_links_sync, keyword)

    def _search_links_sync(self, keyword: str) -> tuple[List[UrlResultItem], List[ImageResultItem]]:
        results: List[UrlResultItem] = []
        images: List[ImageResultItem] = []

        # text search
        with DDGS() as ddgs:
            for item in ddgs.text(keyword, max_results=10):
                title = item.get("title", "Untitled link")
                url = item.get("href")

                if not url:
                    continue

                results.append(
                    UrlResultItem(
                        title=title,
                        url=url,
                        source="duckduckgo",
                        describe=item.get("body", ""),
                    )
                )

        # image search
        with DDGS() as ddgs:
            for item in ddgs.images(
                query=keyword,
                size="Medium",
                type_image="photo",
                max_results=5
            ):
                image_url = item.get("thumbnail") or item.get("image")
                if not image_url:
                    continue

                images.append(
                    ImageResultItem(
                        name=item.get("title") or "Unnamed picture",
                        url=image_url,
                        source="duckduckgo",
                        host_page_url=item.get("url"),
                    )
                )

        return results, images

    async def probe(self) -> bool:
        """
        Minimal availability probe using a dummy query.

        Return True if provider is usable.
        Return False if provider is temporarily unavailable.
        """
        try:
            await self.search_links("test")
            return True

        except Exception as e:
            # DuckDuckGo has no auth concept.
            # Any exception means this provider is temporarily unusable.
            logger.warning(f"[DuckDuckGo] Unavailable: {type(e)}: {e}")
            return False