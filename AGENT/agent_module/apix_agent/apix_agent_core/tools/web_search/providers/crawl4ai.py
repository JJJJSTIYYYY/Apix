""" ⏱
# Install the package
pip install -U crawl4ai

# For pre release versions
pip install crawl4ai --pre

# Run post-installation setup
crawl4ai-setup

# If uv
uv run crawl4ai-setup

# Verify your installation
crawl4ai-doctor

# If uv
uv run crawl4ai-doctor
"""


import asyncio
from typing import List

from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode
from crawl4ai import JsonCssExtractionStrategy

from apix_agent.apix_agent_core.tools.web_search.models import ContentResultItem
from apix_agent.apix_agent_core.tools.web_search.providers.base import BaseSearchProvider
from apix_agent.commons.logger import logger


class Crawl4AIProvider(BaseSearchProvider):
    """
    Crawl4AI service (Python SDK version)

    Supports:
    - url -> content (markdown)
    """

    name = 'Crawl4AI'
    requires_api_key = False
    supports_link_search = False
    supports_content_fetch = True

    async def fetch_content(self, url: str) -> ContentResultItem:
        """
        Fetch page content using crawl4ai AsyncWebCrawler.
        """

        run_config = CrawlerRunConfig(
            # Core
            verbose=False,
            check_robots_txt=True,   # Respect robots.txt 
            # Anti-bot
            simulate_user=True,
            magic=True,
        )
        async with AsyncWebCrawler() as crawler:
            # arun returns a list of CrawlResult
            results = await crawler.arun(
                url=url,
                run_config=run_config,
            )

        if not results:
            raise RuntimeError("Crawl4AI returned empty result")

        result = results[0]

        if not result.success:
            raise RuntimeError(f"Crawl4AI failed: {result.error_message}")

        return ContentResultItem(
            title=result.metadata.get("title", "") if result.metadata else "Untitled content",
            url=url,
            content=result.cleaned_html,
            source="crawl4ai",
            content_type="html",
        )

    async def probe(self) -> bool:
        """
        Probe crawl4ai availability by running a minimal crawl.
        """
        try:
            async with AsyncWebCrawler() as crawler:
                await crawler.arun(
                    urls=["https://example.com"],
                )
            return True
        except Exception as e:
            logger.warning(f"[Crawl4AI] Unavailable: {type(e)}: {e}")
            return False
