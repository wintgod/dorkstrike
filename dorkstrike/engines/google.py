"""Google search engine scraper using Playwright (headless browser).

This engine uses a real Chromium browser to render Google search pages,
bypassing the JavaScript-rendering requirement that blocks simple
requests-based scrapers.  All major dorking tools (DorkEye, DorkScout,
Pagodo) use Google as their primary engine — this module brings that
same capability to DorkStrike.
"""

from __future__ import annotations

import logging
import random
import time
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from .base import BaseEngine
from ..models import SearchResult

logger = logging.getLogger("dorkstrike")

# Playwright is an optional heavy dependency — import lazily
_pw_available: bool | None = None


def _check_playwright() -> bool:
    """Check if Playwright + Chromium are available."""
    global _pw_available
    if _pw_available is not None:
        return _pw_available
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        _pw_available = True
    except ImportError:
        _pw_available = False
    return _pw_available


class GoogleEngine(BaseEngine):
    """Scrape Google search results via Playwright headless browser.

    Google is the gold-standard for dorking — it has the largest index
    and the best support for advanced operators (site:, filetype:,
    intitle:, inurl:, ext:).

    This engine uses Playwright to:
      1. Launch a headless Chromium instance
      2. Navigate to Google search with the dork query
      3. Handle consent screens automatically
      4. Extract results from the rendered DOM
      5. Detect CAPTCHAs / blocks gracefully

    Falls back to a simple requests-based approach if Playwright is
    not installed.
    """

    name = "google"
    _BASE_URL = "https://www.google.com/search"

    def search(
        self,
        query: str,
        pages: int = 1,
        timeout: int = 10,
        session: requests.Session | None = None,
    ) -> list[SearchResult]:
        if _check_playwright():
            return self._search_playwright(query, pages, timeout)
        else:
            logger.warning(
                "[Google] Playwright not installed — falling back to "
                "requests (may not work due to JS requirements). "
                "Install with: pip install playwright && playwright install chromium"
            )
            return self._search_requests(query, pages, timeout, session)

    # ── Playwright-based search ─────────────────────────────────────────

    def _search_playwright(
        self, query: str, pages: int, timeout: int,
    ) -> list[SearchResult]:
        """Search Google using a headless Chromium browser."""
        from playwright.sync_api import sync_playwright

        results: list[SearchResult] = []
        seen_urls: set[str] = set()

        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=True,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                    ],
                )

                context = browser.new_context(
                    viewport={"width": 1366, "height": 768},
                    user_agent=(
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
                    ),
                    locale="en-US",
                    timezone_id="America/New_York",
                )

                # Mask automation signals
                page = context.new_page()
                page.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                """)

                for pg_num in range(pages):
                    start = pg_num * 10
                    url = (
                        f"{self._BASE_URL}?q={quote_plus(query)}"
                        f"&start={start}&num=10&hl=en"
                    )

                    try:
                        page.goto(url, wait_until="domcontentloaded",
                                  timeout=timeout * 1000)
                        # Wait a moment for results to render
                        page.wait_for_timeout(random.randint(1500, 3000))
                    except Exception as exc:
                        logger.warning("[Google] Navigation failed (page %d): %s", pg_num, exc)
                        break

                    # ── Handle Google consent screen ───────────────────
                    self._handle_consent(page)

                    html = page.content()

                    # ── CAPTCHA / block detection ─────────────────────
                    lower = html.lower()
                    if "detected unusual traffic" in lower:
                        logger.warning("[Google] CAPTCHA detected. Stopping.")
                        break
                    if "sorry/index" in page.url.lower():
                        logger.warning("[Google] Blocked (sorry page). Stopping.")
                        break
                    if "recaptcha" in lower and "div.g" not in lower:
                        logger.warning("[Google] reCAPTCHA challenge. Stopping.")
                        break

                    # ── Parse results ─────────────────────────────────
                    soup = BeautifulSoup(html, "lxml")
                    new_results = self._extract_results(
                        soup, query, seen_urls, results,
                    )

                    if new_results == 0:
                        logger.debug(
                            "[Google] No new results on page %d, stopping.", pg_num,
                        )
                        break

                    # Human-like delay between pages
                    if pg_num < pages - 1:
                        time.sleep(random.uniform(2.0, 5.0))

                browser.close()

        except Exception as exc:
            logger.error("[Google] Playwright error: %s", exc)

        logger.debug(
            "[Google] Found %d results for query: %s",
            len(results), query[:80],
        )
        return results

    @staticmethod
    def _handle_consent(page) -> None:
        """Click through Google's consent/cookie banner if present."""
        try:
            # Google consent page: "Before you continue to Google"
            accept_btns = page.query_selector_all(
                "button"
            )
            for btn in accept_btns:
                text = (btn.inner_text() or "").lower()
                if "accept all" in text or "agree" in text or "i agree" in text:
                    btn.click()
                    page.wait_for_timeout(1000)
                    return

            # Form-based consent
            form = page.query_selector("form[action*='consent']")
            if form:
                submit = form.query_selector("button[type='submit'], input[type='submit']")
                if submit:
                    submit.click()
                    page.wait_for_timeout(1000)
        except Exception:
            pass  # Consent handling is best-effort

    def _extract_results(
        self,
        soup: BeautifulSoup,
        query: str,
        seen_urls: set[str],
        results: list[SearchResult],
    ) -> int:
        """Extract organic results from Google's rendered HTML."""
        # Google wraps organic results in div.g
        containers = soup.select("div.g")
        if not containers:
            # Fallback selectors for different Google layouts
            containers = soup.select("div.tF2Cxc") or soup.select("div[data-hveid]")

        new_results = 0
        for container in containers:
            link_tag = container.select_one("a[href]")
            title_tag = container.select_one("h3")
            snippet_tag = (
                container.select_one("div.VwiC3b")
                or container.select_one("span.aCOpRe")
                or container.select_one("div[data-sncf]")
                or container.select_one("div[style='-webkit-line-clamp:2']")
            )

            if not link_tag:
                continue

            raw_url = link_tag.get("href", "")
            clean = self._clean_url(str(raw_url))

            if not clean or clean.startswith("/") or clean.startswith("#"):
                continue

            # Skip Google internal links
            if any(d in clean.lower() for d in [
                "google.com", "google.co.", "gstatic.com",
                "googleapis.com", "youtube.com",
            ]):
                continue

            url_key = clean.lower().rstrip("/")
            if url_key in seen_urls:
                continue
            seen_urls.add(url_key)
            new_results += 1

            results.append(SearchResult(
                url=clean,
                title=self._clean_text(title_tag.get_text() if title_tag else ""),
                snippet=self._clean_text(
                    snippet_tag.get_text() if snippet_tag else ""
                ),
                dork=query,
                engine=self.name,
            ))

        return new_results

    # ── Requests fallback (limited) ────────────────────────────────────

    def _search_requests(
        self,
        query: str,
        pages: int,
        timeout: int,
        session: requests.Session | None,
    ) -> list[SearchResult]:
        """Fallback: try scraping Google with plain requests.

        This rarely works in 2025+ due to JavaScript requirements,
        but may succeed for some queries / regions.
        """
        results: list[SearchResult] = []
        sess = session or requests.Session()
        seen_urls: set[str] = set()

        for pg_num in range(pages):
            start = pg_num * 10
            url = (
                f"{self._BASE_URL}?q={quote_plus(query)}"
                f"&start={start}&num=10&hl=en"
            )

            try:
                resp = sess.get(url, timeout=timeout)
                resp.raise_for_status()
            except requests.RequestException as exc:
                logger.warning("[Google] Request failed (page %d): %s", pg_num, exc)
                break

            lower = resp.text.lower()
            if "detected unusual traffic" in lower or resp.status_code == 429:
                logger.warning("[Google] CAPTCHA/rate-limit detected. Stopping.")
                break

            soup = BeautifulSoup(resp.text, "lxml")
            new_results = self._extract_results(soup, query, seen_urls, results)

            if new_results == 0:
                logger.debug(
                    "[Google] No results on page %d, stopping pagination.", pg_num,
                )
                break

        logger.debug(
            "[Google] Found %d results for query: %s",
            len(results), query[:80],
        )
        return results
