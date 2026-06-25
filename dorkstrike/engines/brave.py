"""Brave Search engine scraper."""

from __future__ import annotations

import logging
import time
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from .base import BaseEngine
from ..models import SearchResult

logger = logging.getLogger("dorkstrike")


class BraveEngine(BaseEngine):
    """Scrape Brave Search results.

    Brave Search supports standard dorking operators (site:, intitle:, inurl:,
    filetype:) and is generally more lenient with automated queries than
    Google or DuckDuckGo.

    Note: Brave frequently returns 429 (rate limit) for automated traffic.
    We disable the session's retry-on-429 to avoid getting stuck in a retry
    loop, and instead handle it gracefully.
    """

    name = "brave"
    _BASE_URL = "https://search.brave.com/search"

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
            offset = page * 10
            params = {
                "q": query,
                "source": "web",
            }
            if offset > 0:
                params["offset"] = str(offset)

            try:
                # Use a shorter timeout — Brave is fast when it responds
                resp = sess.get(
                    self._BASE_URL,
                    params=params,
                    timeout=min(timeout, 12),
                )
                # Handle 429 explicitly (don't let the retry adapter loop)
                if resp.status_code == 429:
                    logger.warning("[Brave] Rate-limited (429). Stopping.")
                    break
                resp.raise_for_status()
            except requests.RequestException as exc:
                err_str = str(exc).lower()
                if "429" in err_str or "too many" in err_str:
                    logger.warning("[Brave] Rate-limited. Stopping.")
                else:
                    logger.warning("[Brave] Request failed (page %d): %s", page, exc)
                break

            # ── Block detection ────────────────────────────────────────
            text_lower = resp.text.lower()
            if "rate limit" in text_lower and len(resp.text) < 5000:
                logger.warning("[Brave] Rate-limit page detected. Stopping.")
                break

            # ── Operator fallback detection ────────────────────────────
            # Brave silently drops operators (site:, filetype:, etc.)
            # when "Too few matches were found" and shows a banner:
            #   "search operators were not applied"
            # The results returned are GENERIC and don't match the dork,
            # so we must discard them to avoid false positives.
            if "search operators were not applied" in text_lower:
                logger.warning(
                    "[Brave] Operators were dropped (too few matches). "
                    "Results are unreliable — skipping."
                )
                break

            soup = BeautifulSoup(resp.text, "lxml")

            # Brave wraps organic results in div#results > div.snippet
            containers = (
                soup.select("div.snippet.fdb")
                or soup.select("div.snippet")
                or soup.select("div[data-type='web']")
            )

            new_results_this_page = 0
            for container in containers:
                link_tag = (
                    container.select_one("a.result-header")
                    or container.select_one("a[href^='http']")
                )
                title_tag = (
                    container.select_one("span.snippet-title")
                    or container.select_one(".title")
                )
                snippet_tag = (
                    container.select_one("p.snippet-description")
                    or container.select_one(".snippet-content")
                    or container.select_one("p")
                )

                if not link_tag:
                    continue

                raw_url = link_tag.get("href", "")
                clean = self._clean_url(str(raw_url))

                if not clean or clean.startswith("/"):
                    continue

                # Skip Brave internal links
                if "brave.com" in clean.lower():
                    continue

                url_key = clean.lower().rstrip("/")
                if url_key in seen_urls:
                    continue
                seen_urls.add(url_key)
                new_results_this_page += 1

                title_text = ""
                if title_tag:
                    title_text = title_tag.get_text()
                elif link_tag:
                    title_text = link_tag.get_text()

                results.append(SearchResult(
                    url=clean,
                    title=self._clean_text(title_text),
                    snippet=self._clean_text(snippet_tag.get_text() if snippet_tag else ""),
                    dork=query,
                    engine=self.name,
                ))

            if not containers or new_results_this_page == 0:
                logger.debug("[Brave] No new results on page %d, stopping.", page)
                break

        logger.debug("[Brave] Found %d results for query: %s", len(results), query[:80])
        return results
