"""Abstract base class for search engines."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from ..models import SearchResult

logger = logging.getLogger("dorkstrike")


class BaseEngine(ABC):
    """Interface that all search engine scrapers must implement."""

    name: str = "base"

    @abstractmethod
    def search(self, query: str, pages: int = 1, timeout: int = 10) -> list[SearchResult]:
        """Execute a search query and return parsed results.

        Args:
            query: The full search query string (already normalized with site:).
            pages: Number of result pages to fetch.
            timeout: HTTP request timeout in seconds.

        Returns:
            List of SearchResult objects.
        """
        ...

    def _clean_url(self, url: str) -> str:
        """Clean and normalize a URL extracted from search results."""
        if not url:
            return ""
        # Remove common tracking redirects
        url = url.strip()
        # Strip Google/Bing redirect wrappers if present
        for prefix in [
            "/url?q=", "/url?sa=t&url=",
            "https://www.google.com/url?q=",
        ]:
            if url.startswith(prefix):
                url = url.split(prefix, 1)[1]
                url = url.split("&", 1)[0]
                break
        return url

    def _clean_text(self, text: str | None) -> str:
        """Clean extracted text — collapse whitespace, strip."""
        if not text:
            return ""
        return " ".join(text.split()).strip()
