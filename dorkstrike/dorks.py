"""Dork loading, normalization, and deduplication for DorkStrike."""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Optional

from .models import DorkEntry

logger = logging.getLogger("dorkstrike")

# Regex to strip existing site: operators
_SITE_RE = re.compile(r"\bsite:\S+", re.IGNORECASE)

# Path to bundled GHDB data
_DATA_DIR = Path(__file__).parent / "data"
_GHDB_PATH = _DATA_DIR / "ghdb.json"


def load_dorks(
    site: str,
    dork_arg: Optional[str] = None,
    dork_list_path: Optional[str] = None,
) -> list[DorkEntry]:
    """Load dorks from CLI, file, or bundled GHDB and normalize them.

    Priority:
        1. dork_list_path (-dl) — file with one dork per line
        2. dork_arg (-d) — comma-separated dorks
        3. Bundled GHDB (data/ghdb.json)

    Args:
        site: Target domain.
        dork_arg: Comma-separated dork string from CLI.
        dork_list_path: Path to dork list file.

    Returns:
        Deduplicated list of normalized DorkEntry objects.

    Raises:
        FileNotFoundError: If dork list or GHDB file not found.
        ValueError: If no dorks loaded.
    """
    raw_dorks: list[tuple[str, str]] = []  # (raw_dork, category)

    if dork_list_path:
        raw_dorks = _load_from_file(dork_list_path)
        logger.info("Loaded %d dorks from file: %s", len(raw_dorks), dork_list_path)
    elif dork_arg:
        raw_dorks = _load_from_arg(dork_arg)
        logger.info("Loaded %d dorks from -d argument", len(raw_dorks))
    else:
        raw_dorks = _load_from_ghdb()
        logger.info("Loaded %d dorks from bundled GHDB", len(raw_dorks))

    if not raw_dorks:
        raise ValueError("No dorks loaded. Provide dorks via -d, -dl, or ensure GHDB data exists.")

    # Normalize and deduplicate
    entries = _normalize(raw_dorks, site)
    logger.info("After normalization & deduplication: %d unique dorks", len(entries))
    return entries


def _load_from_file(path: str) -> list[tuple[str, str]]:
    """Load dorks from a file, one per line. Lines starting with # are comments."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Dork list file not found: {path}")

    dorks: list[tuple[str, str]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                dorks.append((stripped, "Custom"))
    return dorks


def _load_from_arg(dork_arg: str) -> list[tuple[str, str]]:
    """Parse comma-separated dorks from CLI argument."""
    return [
        (d.strip(), "Custom")
        for d in dork_arg.split(",")
        if d.strip()
    ]


def _load_from_ghdb() -> list[tuple[str, str]]:
    """Load dorks from bundled GHDB JSON file."""
    if not _GHDB_PATH.is_file():
        raise FileNotFoundError(
            f"Bundled GHDB not found at {_GHDB_PATH}. "
            "Ensure the data/ghdb.json file is present."
        )

    with open(_GHDB_PATH, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    return [
        (entry["dork"], entry.get("category", "Uncategorized"))
        for entry in data
        if entry.get("dork")
    ]


def _normalize(raw_dorks: list[tuple[str, str]], site: str) -> list[DorkEntry]:
    """Normalize dorks: strip existing site:, inject target, deduplicate.

    Steps:
        1. Strip whitespace
        2. Remove existing site: operators
        3. Prepend site:<target>
        4. Wrap in parentheses if boolean OR/| operators present
        5. Deduplicate (case-insensitive on normalized form)
    """
    seen: set[str] = set()
    entries: list[DorkEntry] = []

    for raw, category in raw_dorks:
        # Strip existing site: operator
        cleaned = _SITE_RE.sub("", raw).strip()
        # Collapse multiple spaces
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        if not cleaned:
            continue

        # If the dork contains boolean operators (OR, |), wrap in parens
        # so the site: constraint applies to ALL clauses, not just the first.
        # e.g. site:target.com (intitle:"admin" OR intitle:"administrator")
        if _has_boolean_or(cleaned):
            normalized = f"site:{site} ({cleaned})"
        else:
            normalized = f"site:{site} {cleaned}"
        key = normalized.lower()

        if key not in seen:
            seen.add(key)
            entries.append(DorkEntry(raw=raw, normalized=normalized, category=category))

    return entries


# Regex to detect boolean OR operators (case-insensitive word "OR" or pipe "|")
_BOOL_OR_RE = re.compile(r'\bOR\b|\|', re.IGNORECASE)


def _has_boolean_or(query: str) -> bool:
    """Check if a dork query contains boolean OR/| operators outside quotes."""
    # Simple approach: check for OR or | that isn't inside quotes
    in_quote = False
    quote_char = None
    i = 0
    text = query

    while i < len(text):
        ch = text[i]

        # Toggle quote state
        if ch in ('"', "'") and not in_quote:
            in_quote = True
            quote_char = ch
            i += 1
            continue
        elif in_quote and ch == quote_char:
            in_quote = False
            quote_char = None
            i += 1
            continue

        if not in_quote:
            # Check for "|"
            if ch == '|':
                return True
            # Check for " OR " (word boundary)
            if text[i:i+4].upper() == ' OR ' and i + 4 <= len(text):
                return True
            # Check for OR at the very start: "OR "
            if i == 0 and text[i:i+3].upper() == 'OR ' and len(text) > 3:
                return True
            # Check for OR at the very end: " OR"
            if text[i:].upper() == ' OR':
                return True

        i += 1

    return False
