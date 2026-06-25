"""Search engine registry for DorkStrike."""

from __future__ import annotations

from .base import BaseEngine
from .bing import BingEngine
from .brave import BraveEngine
from .duckduckgo import DuckDuckGoEngine
from .google import GoogleEngine
from .yahoo import YahooEngine
from .yandex import YandexEngine

# Registry mapping engine names → classes
ENGINE_MAP: dict[str, type[BaseEngine]] = {
    "bing": BingEngine,
    "brave": BraveEngine,
    "duckduckgo": DuckDuckGoEngine,
    "google": GoogleEngine,
    "yahoo": YahooEngine,
    "yandex": YandexEngine,
}


def get_engine(name: str) -> BaseEngine:
    """Instantiate an engine by name.

    Args:
        name: Engine name (case-insensitive).

    Returns:
        Engine instance.

    Raises:
        ValueError: If engine name is unknown.
    """
    key = name.strip().lower()
    cls = ENGINE_MAP.get(key)
    if cls is None:
        raise ValueError(
            f"Unknown engine '{name}'. Available: {', '.join(sorted(ENGINE_MAP.keys()))}"
        )
    return cls()


def list_engines() -> list[str]:
    """Return sorted list of available engine names."""
    return sorted(ENGINE_MAP.keys())
