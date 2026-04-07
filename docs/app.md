# `app.py` — Streamlit UI

## Purpose

Entry point for the web interface. Run with:

```bash
streamlit run app.py
```

## Imports

| Import | Used for |
|--------|----------|
| `os` | Read / set environment variables (`OLLAMA_BASE_URL`, `OLLAMA_MODEL`) |
| `traceback` | Format exception tracebacks in the error expander |
| `requests` | HTTP calls to Ollama's `/api/tags` endpoint for health checks |
| `streamlit` | All UI rendering |
| `dotenv.load_dotenv` | Load `.env` file at startup |
| `src.logger.get_logger` | Structured file + console logging |

## Key Functions

### `check_ollama(model: str) -> tuple[bool, str]`
Pre-flight check before analysis begins.

- Calls `GET {OLLAMA_BASE_URL}/api/tags` with a 5-second timeout.
- Verifies the requested model is in the list of pulled models.
- Returns `(True, "OK")` on success; `(False, user-friendly message)` on failure.

### `_friendly_error(raw: str) -> str`
Converts a raw traceback/exception string into a readable one-liner.

- Detects `Connection refused` / `ConnectError` → actionable Ollama fix message.
- Otherwise finds the last meaningful non-`File`/`^` line of the traceback.

### `render_results(state: dict)`
Renders the complete review output after the graph finishes.

- Displays paper metadata (title, authors, date, categories).
- Shows an overall verdict banner styled with CSS classes (`verdict-pass`, `verdict-cond`, `verdict-fail`).
- Renders five `st.metric` score cards: Consistency, Grammar, Novelty, Fact-Check, Integrity.
- Provides five detail tabs (one per agent).
- Offers a Markdown report download button.

## UI Flow

```
Sidebar (model selector + instructions)
  │
Main area
  │
  ├─ URL input + "Analyze" button
  │
  └─ On click:
        1. check_ollama()  ← pre-flight
        2. Import src.graph (deferred to avoid slow startup)
        3. Stream graph nodes → update progress bar + step indicators
        4. render_results(final_state)
```

## Step Constants

```python
STEPS = [
    ("scrape",       "🌐 Scraping arXiv paper"),
    ("decompose",    "✂️  Decomposing sections"),
    ("consistency",  "🔍 Checking consistency"),
    ("grammar",      "✍️  Evaluating grammar"),
    ("novelty",      "💡 Assessing novelty"),
    ("fact_check",   "✅ Fact-checking claims"),
    ("authenticity", "🔒 Scoring authenticity"),
    ("report",       "📝 Generating report"),
]
```

Each step maps to a LangGraph node name and a display label shown in the progress UI.
