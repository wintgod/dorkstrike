"""Yandex search engine scraper."""

from __future__ import annotations

import logging
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from .base import BaseEngine
from ..models import SearchResult

logger = logging.getLogger("dorkstrike")


class YandexEngine(BaseEngine):
    """Scrape Yandex search results.

    Yandex supports site:, filetype:, intitle:, inurl: operators.
    Falls back to the .ru domain if .com is unreachable.

    Note: Yandex is frequently unreachable from many regions and
    aggressively serves CAPTCHAs.  This engine is designed to fail
    fast and gracefully when Yandex is unavailable.
    """

    name = "yandex"
    _BASE_URLS = [
        "https://yandex.com/search/",
        "https://yandex.ru/search/",
    ]

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

        # Use a tight timeout for Yandex — it either responds fast or not at all
        effective_timeout = min(timeout, 8)

        # Try multiple base URLs (yandex.com, then yandex.ru)
        base_url = self._find_working_base(sess, effective_timeout)
        if not base_url:
            logger.warning("[Yandex] All endpoints unreachable. Skipping.")
            return results

        for page in range(pages):
            url = f"{base_url}?text={quote_plus(query)}&p={page}&lr=84"

            try:
                resp = sess.get(
                    url,
                    timeout=effective_timeout,
                    headers={
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
                        "Referer": base_url,
                    },
                )
                resp.raise_for_status()
            except requests.RequestException as exc:
                logger.warning("[Yandex] Request failed (page %d): %s", page, exc)
                break

            if resp.status_code == 429:
                logger.warning("[Yandex] Rate-limited. Stopping.")
                break

            # Yandex CAPTCHA detection — check URL redirect and page content
            if "captcha" in resp.url.lower() or "showcaptcha" in resp.url.lower():
                logger.warning("[Yandex] CAPTCHA redirect detected. Stopping.")
                break
            if "showcaptcha" in resp.text.lower() or "captcha__image" in resp.text.lower():
                logger.warning("[Yandex] CAPTCHA page detected. Stopping.")
                break

            soup = BeautifulSoup(resp.text, "lxml")

            # Yandex organic results — several possible selectors
            containers = (
                soup.select("li.serp-item")
                or soup.select("div.organic")
                or soup.select("div[data-cid]")
            )

            new_results_this_page = 0
            for container in containers:
                link_tag = (
                    container.select_one("h2 a")
                    or container.select_one("a.organic__url")
                    or container.select_one("a.link")
                    or container.select_one("a[href^='http']")
                )
                snippet_tag = (
                    container.select_one("div.text-container")
                    or container.select_one("div.organic__text")
                    or container.select_one("span.extended-text__full")
                    or container.select_one("div.organic__content-wrapper")
                )

                if not link_tag:
                    continue

                raw_url = link_tag.get("href", "")
                clean = self._clean_url(str(raw_url))

                if not clean or clean.startswith("/"):
                    continue

                # Skip Yandex internal links
                if "yandex." in clean.lower():
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
                logger.debug("[Yandex] No new results on page %d, stopping.", page)
                break

        logger.debug("[Yandex] Found %d results for query: %s", len(results), query[:80])
        return results

    def _find_working_base(self, sess: requests.Session, timeout: int) -> str:
        """Probe base URLs and return the first one that responds.

        Uses a *raw* session (no retry adapter) with a very tight timeout
        (max 5s) to fail fast when Yandex is unreachable.  The main session
        has retry adapters that would double/triple the wait time on
        connection errors — we avoid that here.
        """
        import requests as _req

        probe_timeout = min(timeout, 5)
        probe_sess = _req.Session()
        probe_sess.headers.update(sess.headers)

        for base in self._BASE_URLS:
            try:
                resp = probe_sess.head(base, timeout=probe_timeout, allow_redirects=True)
                if resp.status_code < 500:
                    return base
            except _req.RequestException:
                continue
        return ""
