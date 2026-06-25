"""Yahoo search engine scraper."""

from __future__ import annotations

import json
import logging
import re
from urllib.parse import quote_plus, unquote

import requests
from bs4 import BeautifulSoup

from .base import BaseEngine
from ..models import SearchResult

logger = logging.getLogger("dorkstrike")


class YahooEngine(BaseEngine):
    """Scrape Yahoo search results.

    Yahoo now uses heavy client-side rendering.  To work around that
    we try **two** strategies in order:

    1. **Server-rendered HTML** — parse ``div.algo-sr`` / ``div.dd.algo``
       containers the old way.  Still works in some regions / UA combos.
    2. **Embedded JSON** — Yahoo embeds a ``window.__SERIALIZED_PROPS__``
       blob with pre-rendered result data in some page variants.

    If neither yields results, the engine returns an empty list and
    logs a descriptive warning.
    """

    name = "yahoo"
    _BASE_URL = "https://search.yahoo.com/search"

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

        for page in range(pages):
            b = page * 10 + 1
            url = f"{self._BASE_URL}?p={quote_plus(query)}&b={b}&pz=10&ei=UTF-8"

            try:
                resp = sess.get(
                    url,
                    timeout=timeout,
                    headers={
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.5",
                        "Referer": "https://search.yahoo.com/",
                    },
                )
                resp.raise_for_status()
            except requests.RequestException as exc:
                logger.warning("[Yahoo] Request failed (page %d): %s", page, exc)
                break

            if resp.status_code == 429:
                logger.warning("[Yahoo] Rate-limited. Stopping.")
                break

            # Check for CAPTCHA
            text_lower = resp.text.lower()
            if "are you a human" in text_lower or "recaptcha" in text_lower:
                logger.warning("[Yahoo] CAPTCHA detected. Stopping.")
                break

            soup = BeautifulSoup(resp.text, "lxml")

            # ── Strategy 1: Server-rendered HTML containers ────────────
            new_results_this_page = self._parse_html_results(
                soup, query, seen_urls, results,
            )

            # ── Strategy 2: Embedded JSON ──────────────────────────────
            if new_results_this_page == 0:
                new_results_this_page = self._parse_json_results(
                    resp.text, query, seen_urls, results,
                )

            if new_results_this_page == 0:
                logger.debug("[Yahoo] No new results on page %d, stopping.", page)
                if page == 0:
                    logger.warning(
                        "[Yahoo] Zero results — Yahoo may be using client-side "
                        "rendering that cannot be scraped without a browser."
                    )
                break

        logger.debug("[Yahoo] Found %d results for query: %s", len(results), query[:80])
        return results

    # ── HTML parsing (classic server-rendered layout) ───────────────────

    def _parse_html_results(
        self,
        soup: BeautifulSoup,
        query: str,
        seen_urls: set[str],
        results: list[SearchResult],
    ) -> int:
        """Parse results from server-rendered HTML containers."""
        containers = (
            soup.select("div.algo-sr")
            or soup.select("div.dd.algo")
            or soup.select("div.Sr")
            or soup.select("li div.algo")
        )

        new_results = 0
        for container in containers:
            # ── Extract URL ────────────────────────────────────────
            link_tag = None
            for a_tag in container.select("a[href]"):
                href = a_tag.get("href", "")
                if "r.search.yahoo.com" in href or href.startswith("http"):
                    link_tag = a_tag
                    break

            if not link_tag:
                continue

            raw_url = link_tag.get("href", "")
            clean = self._extract_yahoo_url(str(raw_url))

            if not clean or clean.startswith("/"):
                continue

            # Skip Yahoo internal links
            if "yahoo.com" in clean.lower() and "search" in clean.lower():
                continue

            url_key = clean.lower().rstrip("/")
            if url_key in seen_urls:
                continue
            seen_urls.add(url_key)
            new_results += 1

            # ── Extract title ──────────────────────────────────────
            title_text = ""
            h3 = container.select_one("h3")
            if h3:
                title_span = h3.select_one("span")
                title_text = (title_span or h3).get_text()
            if not title_text:
                title_text = link_tag.get_text()

            # ── Extract snippet ────────────────────────────────────
            snippet_tag = (
                container.select_one("div.compText")
                or container.select_one("div.compText p")
                or container.select_one("p")
                or container.select_one("span.fc-falcon")
            )

            results.append(SearchResult(
                url=clean,
                title=self._clean_text(title_text),
                snippet=self._clean_text(snippet_tag.get_text() if snippet_tag else ""),
                dork=query,
                engine=self.name,
            ))

        return new_results

    # ── JSON parsing (client-side rendered data) ───────────────────────

    _SERIALIZED_RE = re.compile(
        r'window\.__SERIALIZED_PROPS__\s*=\s*(\{.+?\})\s*;?\s*</script',
        re.DOTALL,
    )

    def _parse_json_results(
        self,
        html: str,
        query: str,
        seen_urls: set[str],
        results: list[SearchResult],
    ) -> int:
        """Try to extract results from embedded JSON data."""
        new_results = 0

        m = self._SERIALIZED_RE.search(html)
        if not m:
            return 0

        try:
            data = json.loads(m.group(1))
        except (json.JSONDecodeError, ValueError):
            return 0

        # Navigate the nested structure to find organic results
        search_results = self._dig_results(data)
        for item in search_results:
            url = item.get("url", "") or item.get("link", "") or ""
            title = item.get("title", "") or ""

            clean = self._extract_yahoo_url(url) if url else ""
            if not clean or clean.startswith("/"):
                continue

            if "yahoo.com" in clean.lower() and "search" in clean.lower():
                continue

            url_key = clean.lower().rstrip("/")
            if url_key in seen_urls:
                continue
            seen_urls.add(url_key)
            new_results += 1

            snippet = item.get("abstract", "") or item.get("snippet", "") or ""
            results.append(SearchResult(
                url=clean,
                title=self._clean_text(title),
                snippet=self._clean_text(snippet),
                dork=query,
                engine=self.name,
            ))

        return new_results

    @staticmethod
    def _dig_results(data: dict) -> list[dict]:
        """Recursively dig for a list of result dicts inside nested JSON."""
        # Common keys Yahoo uses for organic results
        for key in ("searchResults", "algorithmicResults", "results", "organic"):
            if key in data and isinstance(data[key], list):
                return data[key]

        # Recurse one level into dict values
        for val in data.values():
            if isinstance(val, dict):
                for key in ("searchResults", "algorithmicResults", "results", "organic"):
                    if key in val and isinstance(val[key], list):
                        return val[key]

        return []

    @staticmethod
    def _extract_yahoo_url(url: str) -> str:
        """Extract actual URL from Yahoo's redirect wrapper."""
        # Yahoo wraps URLs like: https://r.search.yahoo.com/.../RU=<encoded_url>/...
        if "RU=" in url:
            try:
                part = url.split("RU=", 1)[1]
                part = part.split("/RK=", 1)[0]
                return unquote(part)
            except (IndexError, ValueError):
                pass
        return url
