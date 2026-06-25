"""DorkStrike — Advanced Dorking Reconnaissance Tool."""

__version__ = "1.0.0"

import logging
import os
import sys
import time

from .cli import BANNER, parse_args
from .config import build_config
from .dorks import load_dorks
from .executor import execute_scan
from .logger import setup_logging
from .models import ScanSummary
from .reports import generate_csv_report, generate_html_report, generate_json_report

# Box drawing constants — single source of truth for width
_BOX_INNER = 58  # characters between the left and right border


def main(argv: list[str] | None = None) -> int:
    """Main entry point for DorkStrike.

    Orchestrates the full scan lifecycle:
        1. Parse CLI arguments
        2. Validate inputs
        3. Setup logging
        4. Print banner + config summary
        5. Load & normalize dorks
        6. Execute scan (query matrix × engines × workers)
        7. Deduplicate results
        8. Generate reports
        9. Save logs
        10. Print execution summary

    Returns:
        Exit code (0 = success, 1 = error).
    """
    start_time = time.monotonic()

    # ── 1. Parse CLI ────────────────────────────────────────────────────
    try:
        args = parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1
    except Exception as exc:
        print(f"\n[ERROR] {exc}", file=sys.stderr)
        return 1

    # ── 2. Build config (validates engines, formats, proxy list) ────────
    try:
        config = build_config(args)
    except ValueError as exc:
        print(f"\n[ERROR] Configuration error: {exc}", file=sys.stderr)
        return 1

    # ── 3. Setup logging ────────────────────────────────────────────────
    logger = setup_logging(log_file=config.log_file, verbose=config.verbose)

    # ── 4. Banner & config summary ──────────────────────────────────────
    print(BANNER)
    _print_config(config)
    logger.info("DorkStrike v%s started", __version__)
    logger.info("Target: %s", config.site)
    logger.info("Engines: %s", ", ".join(config.engines))
    logger.info("Output: %s", config.output_dir)

    # ── 5. Load & normalize dorks ───────────────────────────────────────
    try:
        dorks = load_dorks(
            site=config.site,
            dork_arg=args.dork,
            dork_list_path=args.dork_list,
        )
    except (FileNotFoundError, ValueError) as exc:
        logger.error("Failed to load dorks: %s", exc)
        print(f"\n[ERROR] {exc}", file=sys.stderr)
        return 1

    print(f"\n  ✓ Loaded {len(dorks)} unique dorks")
    logger.info("Loaded %d unique dorks", len(dorks))

    # ── 6–8. Execute scan ───────────────────────────────────────────────
    print(f"\n  ⚡ Executing {len(dorks)} dorks × {len(config.engines)} engines "
          f"= {len(dorks) * len(config.engines)} queries\n")

    try:
        results = execute_scan(config, dorks)
    except KeyboardInterrupt:
        print("\n\n  ⚠  Scan interrupted by user. Generating partial report...\n")
        logger.warning("Scan interrupted by user")
        results = []

    # ── 9. Generate reports ─────────────────────────────────────────────
    report_files: list[str] = []
    print(f"\n  ✓ {len(results)} unique results found\n")

    try:
        if "html" in config.formats:
            path = generate_html_report(results, config, config.output_dir)
            report_files.append(path)
        if "json" in config.formats:
            path = generate_json_report(results, config, config.output_dir)
            report_files.append(path)
        if "csv" in config.formats:
            path = generate_csv_report(results, config, config.output_dir)
            report_files.append(path)
    except KeyboardInterrupt:
        print("\n  ⚠  Report generation interrupted.")

    # ── 10. Execution summary ───────────────────────────────────────────
    elapsed = time.monotonic() - start_time
    summary = ScanSummary(
        target=config.site,
        engines_used=config.engines,
        total_dorks=len(dorks),
        total_results=len(results),
        unique_urls=len(set(r.url.lower().rstrip("/") for r in results)),
        duration_seconds=elapsed,
        report_files=report_files,
    )

    _print_summary(summary)
    logger.info("Scan completed in %.2f seconds", elapsed)

    return 0


def _print_config(config) -> None:
    """Print scan configuration to console."""
    w = _BOX_INNER
    engines_str = ', '.join(config.engines)
    proxy_str = config.proxy or 'None'
    formats_str = ', '.join(config.formats)

    lines = [
        ("Target",     config.site),
        ("Engines",    engines_str),
        ("Delay",      str(config.delay)),
        ("Rate Limit", f"{config.rate_limit} req/min"),
        ("Threads",    str(config.threads)),
        ("Pages",      str(config.pages)),
        ("Proxy",      proxy_str),
        ("Output",     config.output_dir),
        ("Formats",    formats_str),
    ]

    print(f"  ┌{'─' * w}┐")
    print(f"  │{'SCAN CONFIGURATION':^{w}}│")
    print(f"  ├{'─' * w}┤")
    for label, value in lines:
        content = f"  {label:<12}: {value}"
        print(f"  │{content:<{w}}│")
    print(f"  └{'─' * w}┘")


def _print_summary(summary: ScanSummary) -> None:
    """Print execution summary to console."""
    w = _BOX_INNER
    engines_str = ', '.join(summary.engines_used)
    duration_str = f"{summary.duration_seconds:.2f}s"

    lines = [
        ("Target",        summary.target),
        ("Engines",       engines_str),
        ("Dorks",         str(summary.total_dorks)),
        ("Total Results", str(summary.total_results)),
        ("Unique URLs",   str(summary.unique_urls)),
        ("Duration",      duration_str),
    ]

    print()
    print(f"  ╔{'═' * w}╗")
    print(f"  ║{'EXECUTION SUMMARY':^{w}}║")
    print(f"  ╠{'═' * w}╣")
    for label, value in lines:
        content = f"  {label:<14}: {value}"
        print(f"  ║{content:<{w}}║")
    print(f"  ╠{'═' * w}╣")
    content = f"  {'Reports:'}"
    print(f"  ║{content:<{w}}║")
    for f in summary.report_files:
        fname = os.path.basename(f)
        content = f"    → {fname}"
        print(f"  ║{content:<{w}}║")
    if not summary.report_files:
        content = f"    {'(none)'}"
        print(f"  ║{content:<{w}}║")
    print(f"  ╚{'═' * w}╝")
    print()
