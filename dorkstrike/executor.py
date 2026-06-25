"""Executor — builds query matrix, orchestrates workers, deduplicates results."""

from __future__ import annotations

import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from typing import Optional
from urllib.parse import urlparse

from .engines import get_engine
from .models import DorkEntry, ScanConfig, SearchResult
from .network import (
    ProxyRotator,
    TokenBucket,
    apply_delay,
    create_session,
)

logger = logging.getLogger("dorkstrike")

# Global flag for graceful shutdown
_shutdown_event = threading.Event()


def build_query_matrix(
    engines: list[str],
    dorks: list[DorkEntry],
) -> list[tuple[str, DorkEntry]]:
    """Build the cross-product of engines × dorks."""
    matrix = [(eng, dork) for eng in engines for dork in dorks]
    logger.info(
        "Query matrix: %d engines × %d dorks = %d queries",
        len(engines), len(dorks), len(matrix),
    )
    return matrix


def execute_scan(
    config: ScanConfig,
    dorks: list[DorkEntry],
) -> list[SearchResult]:
    """Execute the full scan across all engines and dorks."""
    _shutdown_event.clear()
    matrix = build_query_matrix(config.engines, dorks)

    if not matrix:
        logger.warning("Empty query matrix — nothing to execute.")
        return []

    # Per-engine rate limiters
    rate_limiters: dict[str, TokenBucket] = {
        eng: TokenBucket(config.rate_limit) for eng in config.engines
    }

    # Proxy rotator
    proxy_rotator: Optional[ProxyRotator] = None
    if config.proxy_list:
        proxy_rotator = ProxyRotator(config.proxy_list)

    # Thread-safe results collection
    all_results: list[SearchResult] = []
    results_lock = threading.Lock()

    # Per-engine result counters
    engine_counts: dict[str, int] = {eng: 0 for eng in config.engines}

    # Progress tracking
    completed = 0
    total = len(matrix)
    progress_lock = threading.Lock()

    def _worker(engine_name: str, dork: DorkEntry) -> None:
        nonlocal completed

        if _shutdown_event.is_set():
            return

        try:
            rate_limiters[engine_name].acquire()

            if _shutdown_event.is_set():
                return

            proxy = config.proxy
            if proxy_rotator:
                proxy = proxy_rotator.next()

            session = create_session(timeout=config.timeout, proxy=proxy)
            apply_delay(config.delay)

            if _shutdown_event.is_set():
                return

            engine = get_engine(engine_name)
            results = engine.search(
                query=dork.normalized,
                pages=config.pages,
                timeout=config.timeout,
                session=session,
            )

            for r in results:
                r.category = dork.category

            with results_lock:
                all_results.extend(results)
                engine_counts[engine_name] += len(results)

        except Exception as exc:
            if not _shutdown_event.is_set():
                logger.error(
                    "[%s] Error processing dork '%s': %s",
                    engine_name, dork.raw[:50], exc,
                )

        finally:
            with progress_lock:
                completed += 1
                pct = (completed / total) * 100
                if not _shutdown_event.is_set():
                    logger.info(
                        "Progress: %d/%d (%.1f%%) — [%s] %s",
                        completed, total, pct, engine_name, dork.raw[:60],
                    )

    max_workers = config.threads * len(config.engines)
    logger.info("Starting execution: %d queries, %d workers", total, max_workers)

    start_time = time.monotonic()
    pool = ThreadPoolExecutor(max_workers=max_workers)
    futures: dict[Future, tuple[str, DorkEntry]] = {}

    try:
        futures = {
            pool.submit(_worker, eng, dork): (eng, dork)
            for eng, dork in matrix
        }

        for future in as_completed(futures):
            if _shutdown_event.is_set():
                break
            exc = future.exception()
            if exc and not _shutdown_event.is_set():
                eng, dork = futures[future]
                logger.error("[%s] Unhandled exception: %s", eng, exc)

    except KeyboardInterrupt:
        _shutdown_event.set()
        print("\n\n  ⚠  Scan interrupted. Collecting partial results...")
        logger.warning("Scan interrupted by user (KeyboardInterrupt)")

    # Force immediate shutdown — cancel all pending, don't wait
    for future in futures:
        future.cancel()
    pool.shutdown(wait=False, cancel_futures=True)

    elapsed = time.monotonic() - start_time
    logger.info("Execution completed in %.2f seconds", elapsed)

    # Print per-engine breakdown
    print("\n  ── Engine Results ──")
    for eng in config.engines:
        count = engine_counts.get(eng, 0)
        icon = "✓" if count > 0 else "✗"
        print(f"    {icon} {eng:<12s}: {count} raw results")
    print()

    # Filter results to target domain only
    filtered = _filter_by_domain(all_results, config.site)
    logger.info(
        "Domain filter: %d total → %d on-target (domain: %s)",
        len(all_results), len(filtered), config.site,
    )

    # Deduplicate results by URL
    deduped = _deduplicate_results(filtered)
    logger.info(
        "Deduplication: %d filtered → %d unique",
        len(filtered), len(deduped),
    )

    return deduped


def _filter_by_domain(results: list[SearchResult], target_site: str) -> list[SearchResult]:
    """Filter results to only include URLs belonging to the target domain."""
    target = target_site.lower().strip()
    if "://" in target:
        target = target.split("://", 1)[1]
    target = target.rstrip("/")

    filtered: list[SearchResult] = []
    for result in results:
        try:
            parsed = urlparse(result.url)
            hostname = (parsed.hostname or "").lower()
            if hostname == target or hostname.endswith("." + target):
                filtered.append(result)
            else:
                logger.debug("Filtered out off-target: %s", result.url[:80])
        except Exception:
            continue
    return filtered


def _deduplicate_results(results: list[SearchResult]) -> list[SearchResult]:
    """Deduplicate results by normalized URL, keeping first occurrence."""
    seen: set[str] = set()
    unique: list[SearchResult] = []

    for result in results:
        key = result.url.lower().rstrip("/")
        if key not in seen:
            seen.add(key)
            unique.append(result)

    return unique
