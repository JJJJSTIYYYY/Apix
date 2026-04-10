"""
Provider registry.

This module ONLY defines provider imports and PROVIDER_REGISTRY.
No routing logic should be placed here.
"""

from typing import Dict, Type

from apix_agent.apix_agent_core.tools.web_search.providers.base import BaseSearchProvider

# ------------------------------------------------------------
# Link search providers (keyword -> urls)
# ------------------------------------------------------------
from apix_agent.apix_agent_core.tools.web_search.providers.duckduckgo import DuckDuckGoProvider
from apix_agent.apix_agent_core.tools.web_search.providers.bing import BingProvider
from apix_agent.apix_agent_core.tools.web_search.providers.google import GoogleProvider
from apix_agent.apix_agent_core.tools.web_search.providers.bocha import BochaProvider
from apix_agent.apix_agent_core.tools.web_search.providers.unifuncs import UniFuncsProvider
from apix_agent.apix_agent_core.tools.web_search.providers.searxng import SearxNGProvider

# ------------------------------------------------------------
# Content fetch providers (urls -> content / urls -> content+urls)
# ------------------------------------------------------------
from apix_agent.apix_agent_core.tools.web_search.providers.tavily import TavilyProvider
from apix_agent.apix_agent_core.tools.web_search.providers.jina import JinaProvider
from apix_agent.apix_agent_core.tools.web_search.providers.crawl4ai import Crawl4AIProvider

# ------------------------------------------------------------
# Provider registry
# ------------------------------------------------------------
PROVIDER_REGISTRY: Dict[str, Type[BaseSearchProvider]] = {
    # ---------- no api key ----------
    "duckduckgo": DuckDuckGoProvider,

    # ---------- link search (api key required) ----------
    # "searxng": SearxNGProvider,  # SearxNG provider requires self-hosted instance, disabled by default
    "bocha": BochaProvider,
    "unifuncs": UniFuncsProvider,
    "bing": BingProvider,
    # "google": GoogleProvider,  # Google provider requires both API key and CSE ID, set CSE ID via set_cx(), disabled by default

    # ---------- content fetch ----------
    "tavily": TavilyProvider,
    "jina": JinaProvider,
    "crawl4ai": Crawl4AIProvider,
}

__all__ = [
    "PROVIDER_REGISTRY",
]
