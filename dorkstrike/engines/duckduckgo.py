"""DuckDuckGo search engine scraper (HTML-only mode)."""

from __future__ import annotations

import logging
import time
from urllib.parse import quote_plus, unquote

import requests
from bs4 import BeautifulSoup

from .base import BaseEngine
from ..models import SearchResult

logger = logging.getLogger("dorkstrike")


class DuckDuckGoEngine(BaseEngine):
    """Scrape DuckDuckGo HTML search results.

    Uses the HTML-only endpoint (html.duckduckgo.com) which is more
    accessible for automated queries. Falls back to the lite endpoint
    if the primary one fails.
    """

    name = "duckduckgo"
    _BASE_URL = "https://html.duckduckgo.com/html/"
    _LITE_URL = "https://lite.duckduckgo.com/lite/"

    def search(
        self,
        query: str,
        pages: int = 1,
        timeout: int = 10,
        session: requests.Session | None = None,
    ) -> list[SearchResult]:
        results: list[SearchResult] = []
        sess = session or requests.Session()
        seen_urls: set[str] = set()

        # Try primary endpoint first, fall back to lite
        for endpoint in [self._BASE_URL, self._LITE_URL]:
            if results:
                break  # Got results from primary, skip lite

            for page in range(pages):
                try:
                    resp = sess.post(
                        endpoint,
                        data={"q": query, "b": str(page * 30), "kl": ""},
                        timeout=timeout,
                        headers={
                            "Content-Type": "application/x-www-form-urlencoded",
                            "Referer": "https://html.duckduckgo.com/",
                        },
                    )
                    resp.raise_for_status()
                except requests.RequestException as exc:
                    logger.warning("[DuckDuckGo] Request failed: %s", exc)
                    break

                if resp.status_code in (429, 202):
                    logger.warning("[DuckDuckGo] Rate-limited (%d). Stopping.", resp.status_code)
                    break

                # Check for actual CAPTCHA or blocking (strict detection)
                if self._is_blocked(resp.text):
                    logger.warning("[DuckDuckGo] Block/CAPTCHA detected on %s.", endpoint)
                    break

                soup = BeautifulSoup(resp.text, "lxml")

                # Primary endpoint uses div.result / a.result__a
                # Lite endpoint uses different selectors
                containers = soup.select("div.result")
                if not containers:
                    # Lite endpoint fallback selectors
                    containers = soup.select("table.result-link") or soup.select("tr")

                new_results_this_page = 0
                for container in containers:
                    link_tag = (
                        container.select_one("a.result__a")
                        or container.select_one("a[href*='uddg=']")
                        or container.select_one("a[href^='http']")
                    )
                    snippet_tag = (
                        container.select_one("a.result__snippet")
                        or container.select_one("td.result-snippet")
                    )

                    if not link_tag:
                        continue

                    raw_url = link_tag.get("href", "")
                    # DDG wraps URLs in a redirect — extract the actual URL
                    clean = self._extract_ddg_url(str(raw_url))

                    if not clean or clean.startswith("/"):
                        continue

                    # Skip DuckDuckGo internal links
                    if "duckduckgo.com" in clean.lower():
                        continue

                    url_key = clean.lower().rstrip("/")
                    if url_key in seen_urls:
                        continue
                    seen_urls.add(url_key)
                    new_results_this_page += 1

                    results.append(SearchResult(
                        url=clean,
                        title=self._clean_text(link_tag.get_text()),
                        snippet=self._clean_text(snippet_tag.get_text() if snippet_tag else ""),
                        dork=query,
                        engine=self.name,
                    ))

                if not containers or new_results_this_page == 0:
                    logger.debug("[DuckDuckGo] No new results on page %d, stopping.", page)
                    break

        logger.debug("[DuckDuckGo] Found %d results for query: %s", len(results), query[:80])
        return results

    @staticmethod
    def _extract_ddg_url(url: str) -> str:
        """Extract real URL from DuckDuckGo redirect wrapper."""
        if "uddg=" in url:
            try:
                param = url.split("uddg=", 1)[1]
                param = param.split("&", 1)[0]
                return unquote(param)
            except (IndexError, ValueError):
                pass
        return url

    @staticmethod
    def _is_blocked(html: str) -> bool:
        """Detect actual DuckDuckGo blocks (not false positives).

        DDG shows a specific interstitial when it detects bot traffic.
        As of 2026, the block page says "bots use DuckDuckGo too" and
        asks the user to complete a duck-selection challenge.
        """
        lower = html.lower()
        # DDG's actual block/CAPTCHA indicators
        if "your request appears to be coming from a bot" in lower:
            return True
        if "bots use duckduckgo" in lower:
            return True
        if "challenge to confirm" in lower and "human" in lower:
            return True
        if "unusual traffic" in lower and len(html) < 5000:
            return True
        return False
