import asyncio

import requests

from apix_agent.apix_agent_core.tools.web_search.models import ContentResultItem
from apix_agent.apix_agent_core.tools.web_search.providers.base import BaseSearchProvider
from apix_agent.commons.logger import logger


class JinaProvider(BaseSearchProvider):
    """
    Jina AI Reader

    Supports:
    - url -> content

    Notes:
    - API key is optional (rate limit / private usage)
    """

    name = 'Jina'
    requires_api_key = False
    supports_link_search = False
    supports_content_fetch = True

    _reader_prefix = "https://r.jina.ai/"

    async def fetch_content(self, url: str) -> ContentResultItem:
        def _fetch_sync() -> ContentResultItem:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            resp = requests.get(
                f"{self._reader_prefix}{url}",
                headers=headers,
                timeout=20,
            )
            resp.raise_for_status()

            return ContentResultItem(
                title="",
                url=url,
                content=resp.text,
                source="jina",
                content_type="markdown",
            )

        return await asyncio.to_thread(_fetch_sync)

    async def probe(self) -> bool:
        """
        Probe by requesting a lightweight known page.
        """
        try:
            await self.fetch_content("https://example.com")
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
            logger.warning(f"[Jina] Unavailable: {type(e)}: {e}")
            return False
