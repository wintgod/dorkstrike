"""CSV report generator for DorkStrike."""

from __future__ import annotations

import csv
import logging
import os
from datetime import datetime

from ..models import ScanConfig, SearchResult

logger = logging.getLogger("dorkstrike")


def generate_csv_report(
    results: list[SearchResult],
    config: ScanConfig,
    output_dir: str,
) -> str:
    """Generate a CSV report.

    Args:
        results: Deduplicated search results.
        config: Scan configuration.
        output_dir: Directory to write the report.

    Returns:
        Path to the generated CSV file.
    """
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"dorkstrike_report_{timestamp}.csv"
    filepath = os.path.join(output_dir, filename)

    fieldnames = ["url", "title", "snippet", "dork", "engine", "category", "timestamp"]

    with open(filepath, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for r in results:
            writer.writerow({
                "url": r.url,
                "title": r.title,
                "snippet": r.snippet,
                "dork": r.dork,
                "engine": r.engine,
                "category": r.category,
                "timestamp": r.timestamp,
            })

    logger.info("CSV report saved: %s", filepath)
    return filepath
