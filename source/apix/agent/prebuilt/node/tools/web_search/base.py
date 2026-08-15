from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class UrlResultItem:
    """
    Result of keyword-based search.
    Used for discovery (title + url only).
    """

    title: str
    url: str
    source: Optional[str] = None
    describe: Optional[str] = None


@dataclass(slots=True)
class ImageResultItem:
    """
    Image result of keyword-based search.
    Used for discovery (title + url only).
    """

    name: str
    url: str
    source: Optional[str] = None
    host_page_url: Optional[str] = None


@dataclass(slots=True)
class ContentResultItem:
    """
    Result of content fetching by URL.
    Used for reading / reasoning.
    """

    title: str
    url: str
    content: str
    source: Optional[str] = None
    content_type: Optional[str] = None
    images: Optional[list[str]] = None
