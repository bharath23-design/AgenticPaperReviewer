# `src/logger.py` — Centralized Logging

## Purpose

Configures the Python root logger once and provides `get_logger(name)` for use throughout the project. Produces both a daily-rotating log file and a console stream.

## Imports

| Import | Used for |
|--------|----------|
| `logging` | Standard Python logging framework |
| `os` | (available but logging config uses `pathlib`) |
| `logging.handlers.TimedRotatingFileHandler` | Daily log file rotation |
| `pathlib.Path` | Cross-platform path construction for log directory |

## Public API

### `get_logger(name: str) -> logging.Logger`

Returns a named logger. Ensures the root logger is configured (idempotent — runs setup only once via `_configured` flag).

**Usage:**
```python
from src.logger import get_logger
log = get_logger(__name__)
log.info("Starting scrape for URL: %s", url)
```

## Log Configuration

| Setting | Value |
|---------|-------|
| Log directory | `<project_root>/logs/` |
| Log file | `logs/app.log` (rotated to `app.log.YYYY-MM-DD`) |
| Rotation schedule | Daily at midnight, 30 days retained |
| File handler level | `DEBUG` |
| Console handler level | `INFO` |
| Format | `%(asctime)s \| %(levelname)-8s \| %(name)-35s \| %(message)s` |

## Noise Suppression

Third-party loggers that produce excessive output are set to `WARNING`:
`httpx`, `httpcore`, `urllib3`, `requests`, `arxiv`, `langchain`, `langchain_core`, `langchain_ollama`, `langgraph`, `watchdog`, `fsevents`.
