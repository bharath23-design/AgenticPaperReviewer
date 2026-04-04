"""
Centralized logging — one log file per day under logs/.

Usage anywhere in the project:
    from src.logger import get_logger
    log = get_logger(__name__)
    log.info("hello")
"""

import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

# Project root = two levels up from this file (src/logger.py → root)
_ROOT = Path(__file__).resolve().parent.parent
_LOG_DIR = _ROOT / "logs"
_LOG_DIR.mkdir(exist_ok=True)

_LOG_FILE = _LOG_DIR / "app.log"          # rotated → app.log.YYYY-MM-DD

_FMT = "%(asctime)s | %(levelname)-8s | %(name)-35s | %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"

# ── Root logger configured once ───────────────────────────────────────────────
_configured = False


def _configure_root() -> None:
    global _configured
    if _configured:
        return

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Daily rotating file handler — rotates at midnight, keeps 30 days
    file_handler = TimedRotatingFileHandler(
        filename=str(_LOG_FILE),
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
        utc=False,
    )
    file_handler.suffix = "%Y-%m-%d"           # logs/app.log.2026-04-03
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(_FMT, _DATE_FMT))

    # Console handler — INFO and above only
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(_FMT, _DATE_FMT))

    root.addHandler(file_handler)
    root.addHandler(console_handler)

    # Silence noisy third-party loggers
    for noisy in ("httpx", "httpcore", "urllib3", "requests", "arxiv",
                  "langchain", "langchain_core", "langchain_ollama",
                  "langgraph", "watchdog", "fsevents"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger, ensuring the root is configured."""
    _configure_root()
    return logging.getLogger(name)