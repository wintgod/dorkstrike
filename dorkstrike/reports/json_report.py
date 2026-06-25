"""JSON report generator for DorkStrike."""

from __future__ import annotations

import json
import logging
import os
from collections import Counter
from datetime import datetime

from ..models import ScanConfig, SearchResult

logger = logging.getLogger("dorkstrike")


def generate_json_report(
    results: list[SearchResult],
    config: ScanConfig,
    output_dir: str,
) -> str:
    """Generate a structured JSON report.

    Args:
        results: Deduplicated search results.
        config: Scan configuration.
        output_dir: Directory to write the report.

    Returns:
        Path to the generated JSON file.
    """
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"dorkstrike_report_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)

    engine_counts = Counter(r.engine for r in results)
    category_counts = Counter(r.category for r in results)

    report = {
        "scan_info": {
            "target": config.site,
            "timestamp": datetime.utcnow().isoformat(),
            "engines": config.engines,
            "dork_count": len(set(r.dork for r in results)),
            "delay": config.delay,
            "rate_limit": config.rate_limit,
        },
        "summary": {
            "total_results": len(results),
            "by_engine": dict(engine_counts),
            "by_category": dict(category_counts),
        },
        "results": [
            {
                "url": r.url,
                "title": r.title,
                "snippet": r.snippet,
                "dork": r.dork,
                "engine": r.engine,
                "category": r.category,
                "timestamp": r.timestamp,
            }
            for r in results
        ],
    }

    with open(filepath, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)

    logger.info("JSON report saved: %s", filepath)
    return filepath
