# Logging System

## Overview

All logging is centralised in `src/logger.py`. Every module gets its own named logger via a single call — no configuration duplication.

```python
from src.logger import get_logger
log = get_logger(__name__)
```

---

## Log File Location

```
AgenticPaperReviewer/
└── logs/
    ├── app.log              ← today's active log file
    ├── app.log.2026-04-03   ← yesterday (auto-rotated)
    ├── app.log.2026-04-02
    └── ...                  ← up to 30 days retained
```

> `logs/` is in `.gitignore` — log files are never committed to the repository.

---

## Log Format

```
YYYY-MM-DD HH:MM:SS | LEVEL    | module.path                         | message
```

Example output:
```
2026-04-03 11:06:49 | INFO     | src.scraper                         | Starting scrape for URL: https://arxiv.org/pdf/1706.03762
2026-04-03 11:06:49 | INFO     | src.scraper                         | Metadata fetched — title: Attention Is All You Need | authors: 8
2026-04-03 11:06:49 | INFO     | src.scraper                         | HTML scrape succeeded for 1706.03762 — 41129 chars
2026-04-03 11:06:49 | INFO     | src.decomposer                      | Decomposing paper — input text: 41129 chars
2026-04-03 11:06:49 | INFO     | src.decomposer                      | Regex found 5 meaningful sections: [...]
2026-04-03 11:06:49 | INFO     | src.graph                           | >>> Node START: consistency
2026-04-03 11:06:52 | INFO     | src.agents.consistency_agent...     | LLM response received — 312 chars in 3.1s
2026-04-03 11:06:52 | INFO     | src.graph                           | <<< Node DONE:  consistency (3.2s)
```

---

## Log Levels

| Level | Where | What |
|-------|-------|------|
| `DEBUG` | File only | arXiv ID extraction, text truncation decisions, JSON parse path taken |
| `INFO` | File + Console | Node start/done, LLM invocations, section sizes, scrape strategy used |
| `WARNING` | File + Console | Fallback strategies triggered, JSON parse failures, empty sections |
| `ERROR` | File + Console | Node failures, Ollama connection refused, paper not found |

---

## Rotation Policy

Configured with Python's `TimedRotatingFileHandler`:

| Setting | Value |
|---------|-------|
| Rotation trigger | Midnight (local time) |
| Suffix format | `YYYY-MM-DD` |
| Retention | 30 days |
| Encoding | UTF-8 |

---

## What Each Module Logs

### `src/scraper.py`
| Event | Level |
|-------|-------|
| Scrape started (URL) | INFO |
| arXiv ID extracted | DEBUG |
| Metadata fetched (title, author count) | INFO |
| HTML version attempt + result | DEBUG / INFO / WARNING |
| Abstract page fallback | DEBUG / INFO |
| All strategies failed → raw abstract | WARNING |
| Final char count | INFO |

### `src/decomposer.py`
| Event | Level |
|-------|-------|
| Input text size | INFO |
| Number of sections found by regex | INFO |
| LLM fallback triggered | INFO |
| Methodology empty → full text fallback | WARNING |
| Final section sizes | INFO |

### `src/agents/base_agent.py` (inherited by all agents)
| Event | Level |
|-------|-------|
| Agent initialised (model, base URL) | DEBUG |
| Text truncated (from/to char count) | DEBUG |
| LLM invoked (model, estimated tokens) | INFO |
| LLM response received (chars, elapsed) | INFO |
| JSON parsed successfully | DEBUG |
| JSON parse failed → defaults used | WARNING |

### `src/graph.py`
| Event | Level |
|-------|-------|
| Review started (URL, model) | INFO |
| Node start (`>>> Node START: <name>`) | INFO |
| Node complete with elapsed time | INFO |
| Node error with elapsed time | ERROR |
| Full traceback on node error | DEBUG |
| Review complete (total elapsed) | INFO |
| Review failed (error summary) | ERROR |

### `app.py`
| Event | Level |
|-------|-------|
| Ollama pre-flight failed (reason) | ERROR |
| Ollama pre-flight passed | INFO |
| Pipeline error (first 300 chars) | ERROR |

---

## Silenced Third-Party Loggers

These are set to `WARNING` to avoid log noise:

- `httpx`, `httpcore` — HTTP client internals
- `urllib3`, `requests` — HTTP library internals
- `arxiv` — arXiv API client
- `langchain`, `langchain_core`, `langchain_ollama` — LangChain internals
- `langgraph` — LangGraph internals
- `watchdog`, `fsevents` — Streamlit file watcher and macOS filesystem event internals

---

## Using the Logger in New Modules

```python
from src.logger import get_logger

log = get_logger(__name__)

def my_function():
    log.info("Starting something important")
    log.debug("Verbose detail: %s", some_value)
    try:
        do_something()
    except Exception as e:
        log.error("Something failed: %s", e)
```

> Always use `%s` style formatting (not f-strings) in log calls.  
> The logger only formats the string if the message will actually be emitted — saving CPU when DEBUG is filtered.
