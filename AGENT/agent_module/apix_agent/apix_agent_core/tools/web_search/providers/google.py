import asyncio
from typing import List
import requests

from apix_agent.apix_agent_core.tools.web_search.models import UrlResultItem
from apix_agent.apix_agent_core.tools.web_search.providers.base import BaseSearchProvider
from apix_agent.commons.logger import logger


class GoogleProvider(BaseSearchProvider):
    """
    Google Custom Search API

    Supports:
    - keyword -> urls

    Notes:
    - Requires BOTH api_key and cse_id
    """

    name = "Google"
    requires_api_key = True
    supports_link_search = True
    supports_content_fetch = False

    API_ENDPOINT = "https://www.googleapis.com/customsearch/v1"

    def __init__(
        self,
        api_key: str | None = None,
        cse_id: str | None = None,
    ):
        super().__init__(api_key=api_key)
        self.cse_id = cse_id

    # --------------------------------------------------
    # keyword -> urls
    # --------------------------------------------------
    async def search_links(self, keyword: str) -> List[UrlResultItem]:
        """
        Search links using Google Custom Search API.

        This method is async but internally uses requests,
        so the blocking HTTP call is executed in a worker thread.
        """
        if not self.api_key or not self.cse_id:
            raise RuntimeError("GoogleProvider requires api_key and cse_id")

        return await asyncio.to_thread(self._search_links_sync, keyword)

    def _search_links_sync(self, keyword: str) -> List[UrlResultItem]:
        """
        Synchronous implementation of link search.
        """
        params = {
            "key": self.api_key,
            "cx": self.cse_id,
            "q": keyword,
            "num": 10,
        }

        resp = requests.get(
            self.API_ENDPOINT,
            params=params,
            timeout=15,
        )
        resp.raise_for_status()

        data = resp.json()
        results: List[UrlResultItem] = []

        for item in data.get("items", []):
            url = item.get("link")
            if not url:
                continue

            results.append(
                UrlResultItem(
                    title=item.get("title", "Untitled link"),
                    url=url,
                    source="google",
                )
            )

        return results

    # --------------------------------------------------
    # probe
    # --------------------------------------------------
    async def probe(self) -> bool:
        """
        Minimal auth probe using a dummy query.

        Return True if provider is usable.
        Return False if provider is reachable but not authorized
        or configuration is incomplete.
        Raise PermissionError if api_key is invalid.
        """
        # Missing config should NOT raise:
        # router will treat this provider as unavailable.
        if not self.api_key or not self.cse_id:
            return False

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
            logger.warning(f"[Google] Unavailable: {type(e)}: {e}")
            return False

    def set_cx(self, cse_id: str) -> None:
        """
        Set Custom Search Engine ID (cx).
        """
        self.cse_id = cse_id
