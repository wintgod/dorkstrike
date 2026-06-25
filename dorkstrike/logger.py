"""Logging setup for DorkStrike."""

from __future__ import annotations

import logging
import os
import sys


LOG_FORMAT = "[%(asctime)s] [%(levelname)-8s] [%(module)-12s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(log_file: str = "dorkstrike.log", verbose: bool = False) -> logging.Logger:
    """Configure dual-handler logging (file + console).

    Args:
        log_file: Path to the log file.
        verbose: If True, console shows DEBUG; otherwise INFO.

    Returns:
        Configured root logger for the dorkstrike package.
    """
    logger = logging.getLogger("dorkstrike")
    logger.setLevel(logging.DEBUG)

    # Prevent duplicate handlers on repeated calls
    if logger.handlers:
        return logger

    # ── File handler — always DEBUG ─────────────────────────────────────
    log_dir = os.path.dirname(log_file)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    logger.addHandler(file_handler)

    # ── Console handler ─────────────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    logger.addHandler(console_handler)

    return logger
