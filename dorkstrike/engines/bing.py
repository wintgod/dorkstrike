"""Bing search engine scraper."""

from __future__ import annotations

import logging
import re
import time
from urllib.parse import quote_plus, unquote

import requests
from bs4 import BeautifulSoup

from .base import BaseEngine
from ..models import SearchResult

logger = logging.getLogger("dorkstrike")


class BingEngine(BaseEngine):
    """Scrape Bing search results.

    Bing aggressively serves JavaScript challenges to automated traffic.
    We employ a multi-step warm-up strategy:

      1. Hit the Bing homepage to collect session cookies (MUID, etc.).
      2. Perform an innocuous "warmup" search to build session trust.
      3. Then issue the actual dork query.

    If Bing still presents a challenge page (``#challenge-stage`` or
    explicit "solve the challenge" text), we log a warning and return
    empty results gracefully.
    """

    name = "bing"
    _BASE_URL = "https://www.bing.com/search"

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

        # ── Step 0: warm up cookies & session trust ─────────────────
        self._warm_cookies(sess, timeout)

        for page in range(pages):
            first = page * 10 + 1
            url = f"{self._BASE_URL}?q={quote_plus(query)}&first={first}&FORM=PERE"

            try:
                resp = sess.get(
                    url,
                    timeout=timeout,
                    headers={
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.9",
                        "Referer": "https://www.bing.com/",
                        "Sec-Fetch-Dest": "document",
                        "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-Site": "same-origin",
                        "Cache-Control": "max-age=0",
                    },
                )
                resp.raise_for_status()
            except requests.RequestException as exc:
                logger.warning("[Bing] Request failed (page %d): %s", page, exc)
                break

            if resp.status_code == 429:
                logger.warning("[Bing] Rate-limited. Stopping.")
                break

            # ── Real block detection (strict) ──────────────────────────
            if self._is_challenge_page(resp.text):
                logger.warning("[Bing] JS challenge / block page detected. Stopping.")
                break

            soup = BeautifulSoup(resp.text, "lxml")

            # Bing organic results — try multiple selectors
            containers = (
                soup.select("li.b_algo")
                or soup.select("div.b_algo")
                or soup.select("ol#b_results li")
            )

            new_results_this_page = 0
            for container in containers:
                link_tag = (
                    container.select_one("h2 a")
                    or container.select_one("h3 a")
                    or container.select_one("a[href^='http']")
                )
                snippet_tag = (
                    container.select_one("div.b_caption p")
                    or container.select_one("p")
                    or container.select_one("div.b_caption")
                )

                if not link_tag:
                    continue

                raw_url = link_tag.get("href", "")
                clean = self._clean_url(str(raw_url))

                if not clean or clean.startswith("/"):
                    continue

                # Skip Bing internal / ad links
                if "bing.com" in clean.lower() or "microsoft.com" in clean.lower():
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
                logger.debug("[Bing] No new results on page %d, stopping.", page)
                break

        logger.debug("[Bing] Found %d results for query: %s", len(results), query[:80])
        return results

    # ── Helpers ─────────────────────────────────────────────────────────

    @staticmethod
    def _warm_cookies(sess: requests.Session, timeout: int) -> None:
        """Hit Bing homepage and do a benign warmup search to collect
        session cookies (MUID etc.) and build session trust.

        This often prevents the JS challenge on subsequent search requests.
        """
        try:
            # Step 1: Homepage visit
            sess.get(
                "https://www.bing.com/",
                timeout=min(timeout, 8),
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                },
            )
            time.sleep(0.5)

            # Step 2: Warmup search (generic query to build cookie trust)
            sess.get(
                "https://www.bing.com/search?q=weather+today&FORM=HDRSC2",
                timeout=min(timeout, 8),
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Referer": "https://www.bing.com/",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "same-origin",
                },
            )
            time.sleep(0.3)
        except requests.RequestException:
            pass  # Not fatal — we'll try the search anyway

    @staticmethod
    def _is_challenge_page(html: str) -> bool:
        """Detect an *actual* JS challenge / CAPTCHA page from Bing.

        Bing's normal search pages contain the word 'captcha' inside
        JavaScript config blobs — that's *not* a real block.  We only
        flag pages that have the visible challenge prompt or the
        ``#challenge-stage`` element.
        """
        lower = html.lower()
        # The explicit user-facing challenge text
        if "please solve the challenge below" in lower:
            return True
        if "solve the challenge" in lower and "challenge-stage" in lower:
            return True
        # Genuine unusual-traffic interstitial (not embedded in JS config)
        if "unusual traffic from your computer" in lower:
            return True
        return False
