import asyncio
from typing import List
import requests

from apix_agent.apix_agent_core.tools.web_search.models import ImageResultItem, UrlResultItem
from apix_agent.apix_agent_core.tools.web_search.providers.base import BaseSearchProvider
from apix_agent.commons.logger import logger


class UniFuncsProvider(BaseSearchProvider):
    """
    UniFuncs search provider.

    Supports:
    - keyword -> urls
    - keyword -> images

    Notes:
    - API key is required.
    - Good Chinese search fallback.
    """

    name = "UniFuncs"
    requires_api_key = True
    supports_link_search = True
    supports_content_fetch = False

    API_ENDPOINT = "https://api.unifuncs.com/api/web-search/search"

    # --------------------------------------------------
    # keyword -> urls
    # --------------------------------------------------
    async def search_links(self, keyword: str) -> tuple[List[UrlResultItem], List[ImageResultItem]]:
        return await asyncio.to_thread(self._search_links_sync, keyword)

    def _search_links_sync(self, keyword: str) -> tuple[List[UrlResultItem], List[ImageResultItem]]:
        """
        Synchronous UniFuncs link search implementation.
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "query": keyword,
            "page": 1,
            "count": 10,
            "includeImages": True,
        }

        resp = requests.post(
            self.API_ENDPOINT,
            json=payload,
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()

        data = resp.json()
        payload_data = data.get("data", {})

        results: List[UrlResultItem] = []
        images: List[ImageResultItem] = []

        for item in payload_data.get("webPages", []):
            url = item.get("url")
            if not url:
                continue

            results.append(
                UrlResultItem(
                    title=item.get("name", "Untitled link"),
                    url=url,
                    source="unifuncs",
                    describe=item.get("summary") or item.get("snippet", ""),
                )
            )

        for index, item in enumerate(payload_data.get("images", []), start=1):
            image_url = item.get("thumbnailUrl") or item.get("contentUrl")
            if not image_url:
                continue

            images.append(
                ImageResultItem(
                    name=f"Image {index}",
                    url=image_url,
                    source="unifuncs",
                    host_page_url=item.get("hostPageUrl"),
                )
            )

        return results, images

    # --------------------------------------------------
    # probe
    # --------------------------------------------------
    async def probe(self) -> bool:
        """
        Minimal auth / availability probe using a dummy query.

        Return True if provider is usable.
        Return False if unauthorized, unreachable, or temporarily unavailable.
        """
        try:
            await self.search_links("test")
            return True

        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code in (401, 403):
                return False
            return False

        except Exception as e:
            logger.warning(f"[UniFuncs] Unavailable: {type(e)}: {e}")
            return False