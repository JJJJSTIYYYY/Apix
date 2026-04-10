from abc import ABC, abstractmethod
from typing import List, Optional

from apix_agent.apix_agent_core.tools.web_search.models import UrlResultItem, ContentResultItem, ImageResultItem


class BaseSearchProvider(ABC):
    """
    Base class for all search providers.

    Design principles:
    - Provider should be stateless (except api_key / client)
    - Capability is declared by overriding methods
    - Router decides which provider to use
    """
    name: str = 'base'

    #: Whether this provider requires an API key
    requires_api_key: bool = False

    #: Whether this provider supports keyword -> url search
    supports_link_search: bool = True

    #: Whether this provider supports url -> content fetch
    supports_content_fetch: bool = False

    def __init__(self, api_key: Optional[str] = None):
        """
        :param api_key: API key if required by provider
        """
        self.api_key = api_key

        if self.requires_api_key and not api_key:
            raise ValueError(
                f"{self.__class__.__name__} requires api_key, but none was provided"
            )

    # ============================================================
    # Keyword -> URLs
    # ============================================================
    async def search_links(self, keyword: str) -> tuple[List[UrlResultItem], List[ImageResultItem]] | List[UrlResultItem]:
        """
        Perform keyword-based search.

        Must be implemented by providers that support link search.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support search_links"
        )

    # ============================================================
    # URLs -> Content
    # ============================================================
    async def fetch_content(self, url: str) -> ContentResultItem:
        """
        Fetch and extract content from a URL.

        Providers that support content fetching SHOULD override this.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support fetch_content"
        )

    # ============================================================
    # Connectivity / Authorization Probe
    # ============================================================
    async def probe(self) -> bool:
        """
        Check whether the provider is reachable and authorized.

        Contract:
        - Return True  -> provider is usable
        - Return False -> authorization failed (401 / 403)
        - Raise       -> network / service / unexpected error

        Router relies on this method for auto-selection.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} does not implement probe()"
        )

    @classmethod
    def supports_task(cls, task_type: str) -> bool:
        """
        Check whether this provider supports the given task type.

        :param task_type: "link" or "content"
        :return: True if supported, False otherwise
        """
        if task_type == "link":
            return cls.supports_link_search
        elif task_type == "content":
            return cls.supports_content_fetch
        else:
            return False