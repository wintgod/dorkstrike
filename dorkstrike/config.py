"""Configuration factory for DorkStrike."""

from __future__ import annotations

import os
from argparse import Namespace

from .models import ScanConfig


VALID_ENGINES = {"bing", "brave", "duckduckgo", "google", "yahoo", "yandex"}
VALID_FORMATS = {"html", "json", "csv"}


def build_config(args: Namespace) -> ScanConfig:
    """Build a ScanConfig from parsed CLI arguments.

    Args:
        args: Parsed argparse namespace.

    Returns:
        Fully validated ScanConfig instance.

    Raises:
        ValueError: If configuration values are invalid.
    """
    # Parse engines
    engines = [e.strip().lower() for e in args.engines.split(",")]
    for eng in engines:
        if eng not in VALID_ENGINES:
            raise ValueError(
                f"Unknown engine '{eng}'. Valid engines: {', '.join(sorted(VALID_ENGINES))}"
            )

    # Parse formats
    formats = [f.strip().lower() for f in args.format.split(",")]
    for fmt in formats:
        if fmt not in VALID_FORMATS:
            raise ValueError(
                f"Unknown format '{fmt}'. Valid formats: {', '.join(sorted(VALID_FORMATS))}"
            )

    # Load proxy list
    proxy_list: list[str] = []
    if args.proxy_list:
        if not os.path.isfile(args.proxy_list):
            raise ValueError(f"Proxy list file not found: {args.proxy_list}")
        with open(args.proxy_list, "r", encoding="utf-8") as fh:
            proxy_list = [
                line.strip() for line in fh if line.strip() and not line.startswith("#")
            ]
        if not proxy_list:
            raise ValueError(f"Proxy list file is empty: {args.proxy_list}")

    return ScanConfig(
        site=args.site,
        engines=engines,
        delay=args.delay,
        rate_limit=args.rate_limit,
        threads=args.threads,
        timeout=args.timeout,
        pages=args.pages,
        proxy=args.proxy,
        proxy_list=proxy_list,
        output_dir=args.output,
        formats=formats,
        log_file=args.log_file,
        verbose=args.verbose,
    )
