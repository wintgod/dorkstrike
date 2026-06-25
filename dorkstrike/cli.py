"""CLI argument parsing and validation for DorkStrike."""

from __future__ import annotations

import argparse
import sys


BANNER = r"""
    ____             __   _____ __       _ __       
   / __ \____  _____/ /__/ ___// /______(_) /_____  
  / / / / __ \/ ___/ //_/\__ \/ __/ ___/ / //_/ _ \ 
 / /_/ / /_/ / /  / ,<  ___/ / /_/ /  / / ,< /  __/ 
/_____/\____/_/  /_/|_|/____/\__/_/  /_/_/|_|\___/  

        [  Dorking Reconnaissance Tool  ]
              [ v1.0.0 — by W1N7G0D ]
"""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse and validate CLI arguments.

    Args:
        argv: Argument list (defaults to sys.argv[1:]).

    Returns:
        Parsed namespace.

    Raises:
        SystemExit: On validation failure.
    """
    parser = argparse.ArgumentParser(
        prog="dorkstrike",
        description="DorkStrike — Advanced Google Dorking Reconnaissance Tool",
        epilog="Example: dorkstrike -s example.com -e google,bing --delay 3",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # ── Target ──────────────────────────────────────────────────────────
    parser.add_argument(
        "-s", "--site",
        type=str,
        required=True,
        help="Target domain (e.g. example.com) [REQUIRED]",
    )

    # ── Dork source (mutually exclusive) ────────────────────────────────
    parser.add_argument(
        "-d", "--dork",
        type=str,
        default=None,
        help="Single dork or comma-separated list of dorks",
    )
    parser.add_argument(
        "-dl", "--dork-list",
        type=str,
        default=None,
        help="Path to a file containing dorks (one per line)",
    )

    # ── Engine & execution ──────────────────────────────────────────────
    parser.add_argument(
        "-e", "--engines",
        type=str,
        default="google,brave,duckduckgo",
        help="Comma-separated search engines (default: google,brave,duckduckgo). "
             "Available: google,brave,duckduckgo,bing,yahoo,yandex",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Delay between requests in seconds (default: 2.0)",
    )
    parser.add_argument(
        "--rate-limit",
        type=int,
        default=15,
        help="Max requests per minute per engine (default: 15)",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=3,
        help="Worker threads per engine (default: 3)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=15,
        help="HTTP request timeout in seconds (default: 15)",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=3,
        help="Max result pages to fetch per query (default: 3)",
    )

    # ── Output ──────────────────────────────────────────────────────────
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="./results",
        help="Output directory for reports (default: ./results)",
    )
    parser.add_argument(
        "-f", "--format",
        type=str,
        default="html",
        help="Report formats: html,json,csv (default: html)",
    )

    # ── Proxy ───────────────────────────────────────────────────────────
    parser.add_argument(
        "-p", "--proxy",
        type=str,
        default=None,
        help="Single proxy URL (http:// or socks5://)",
    )
    parser.add_argument(
        "-pl", "--proxy-list",
        type=str,
        default=None,
        help="Path to file containing proxy URLs for rotation",
    )

    # ── Logging ─────────────────────────────────────────────────────────
    parser.add_argument(
        "--log-file",
        type=str,
        default="dorkstrike.log",
        help="Log file path (default: dorkstrike.log)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        default=False,
        help="Enable verbose console output",
    )

    args = parser.parse_args(argv)

    # ── Validation ──────────────────────────────────────────────────────
    # -d and -dl are mutually exclusive
    if args.dork is not None and args.dork_list is not None:
        raise Exception(
            "Options -d/--dork and -dl/--dork-list are mutually exclusive. "
            "Use one or the other, not both."
        )

    return args
