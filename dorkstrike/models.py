"""Data models for DorkStrike."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class DorkEntry:
    """Represents a single dork query."""

    raw: str
    normalized: str = ""
    category: str = "Custom"

    def __hash__(self) -> int:
        return hash(self.normalized.lower())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DorkEntry):
            return NotImplemented
        return self.normalized.lower() == other.normalized.lower()


@dataclass
class SearchResult:
    """A single search result returned by an engine."""

    url: str
    title: str
    snippet: str
    dork: str
    engine: str
    category: str = "Custom"
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def __hash__(self) -> int:
        return hash(self.url.lower().rstrip("/"))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SearchResult):
            return NotImplemented
        return self.url.lower().rstrip("/") == other.url.lower().rstrip("/")


@dataclass
class ScanConfig:
    """Full scan configuration built from CLI arguments."""

    site: str
    engines: list[str] = field(default_factory=lambda: [
        "google", "brave", "duckduckgo"
    ])
    delay: float = 2.0
    rate_limit: int = 15
    threads: int = 3
    timeout: int = 10
    pages: int = 3
    proxy: Optional[str] = None
    proxy_list: list[str] = field(default_factory=list)
    output_dir: str = "./results"
    formats: list[str] = field(default_factory=lambda: ["html", "json", "csv"])
    log_file: str = "dorkstrike.log"
    verbose: bool = False


@dataclass
class ScanSummary:
    """Execution summary displayed at the end of a scan."""

    target: str = ""
    engines_used: list[str] = field(default_factory=list)
    total_dorks: int = 0
    total_results: int = 0
    unique_urls: int = 0
    duration_seconds: float = 0.0
    report_files: list[str] = field(default_factory=list)
    errors: int = 0
