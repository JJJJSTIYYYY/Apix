import asyncio
from typing import List
import requests

from apix_agent.apix_agent_core.tools.web_search.models import ImageResultItem, UrlResultItem
from apix_agent.apix_agent_core.tools.web_search.providers.base import BaseSearchProvider
from apix_agent.commons.logger import logger


class BingProvider(BaseSearchProvider):
    """
    Bing Web Search API

    Supports:
    - keyword -> urls
    """

    name = "Bing"
    requires_api_key = True
    supports_link_search = True
    supports_content_fetch = False

    API_ENDPOINT = "https://api.bing.microsoft.com/v7.0/search"

    async def search_links(self, keyword: str) -> tuple[List[UrlResultItem], List[ImageResultItem]]:
        """
        Search links using Bing Web Search API.

        This method is async but internally uses requests,
        so the blocking HTTP call is executed in a worker thread.
        """
        return await asyncio.to_thread(self._search_links_sync, keyword)

    def _search_links_sync(self, keyword: str) -> tuple[List[UrlResultItem], List[ImageResultItem]]:
        """
        Synchronous implementation of link search.
        """
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
        }
        params = {
            "q": keyword,
            "count": 10,
        }

        resp = requests.get(
            self.API_ENDPOINT,
            headers=headers,
            params=params,
            timeout=15,
        )
        resp.raise_for_status()

        data = resp.json()

        results: List[UrlResultItem] = []
        images: List[ImageResultItem] = []

        for item in data.get("webPages", {}).get("value", []):
            url = item.get("url")
            if not url:
                continue

            results.append(
                UrlResultItem(
                    title=item.get("name", "Untitled link"),
                    url=url,
                    source="bing",
                    describe=item.get("snippet", ""),
                )
            )

        for item in data.get("images", {}).get("value", []):
            image_url = item.get("thumbnailUrl") or item.get("contentUrl")
            if not image_url:
                continue

            images.append(
                ImageResultItem(
                    name=item.get("name") or "Unnamed picture",
                    url=image_url,
                    source="bing",
                    host_page_url=item.get("hostPageUrl"),
                )
            )

        return results, images

    async def probe(self) -> bool:
        """
        Minimal auth probe using a dummy query.

        Return True if provider is usable.
        Return False if provider is reachable but not authorized.
        Raise PermissionError if api_key is invalid.
        """
        try:
            await self.search_links("test")
            return True

        except requests.HTTPError as e:
            response = getattr(e, "response", None)
            if response is not None and response.status_code in (401, 403):
                # Explicit auth failure: key is invalid
                raise PermissionError("Invalid or unauthorized API key")

            # Other HTTP errors mean provider is temporarily unusable
            return False

        except Exception as e:
            # Network errors / timeouts / unexpected failures
            logger.warning(f"[Bing] Unavailable: {type(e)}: {e}")
            return False
