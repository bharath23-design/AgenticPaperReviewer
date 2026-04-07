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
| `src.graph.create_review_graph` | Builds the compiled LangGraph pipeline at import time |
| `src.graph.ReviewState` | TypedDict used to construct the initial state dict |

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
        2. create_review_graph() → compiled graph
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

## Graph Usage

`create_review_graph` and `ReviewState` are imported at the top level (module load time).

When **Analyze** is clicked, the graph is instantiated and streamed:

```python
graph = create_review_graph()

initial_state: ReviewState = {
    "url": url.strip(),
    "model_name": model_name,
    "paper_metadata": {},
    "paper_text": "",
    "abstract": "",
    "sections": {},
    "consistency_result": {},
    "grammar_result": {},
    "novelty_result": {},
    "fact_check_result": {},
    "authenticity_result": {},
    "final_report": "",
    "current_step": "starting",
    "error": None,
}

for step_output in graph.stream(initial_state):
    node_name = list(step_output.keys())[0]   # e.g. "scrape", "consistency"
    state_update = step_output[node_name]      # partial state dict from that node
    final_state.update(state_update)           # accumulated into final_state
```

Each iteration of `graph.stream()` yields one node's output. The UI:
- Advances the progress bar (`len(completed) / len(STEPS)`)
- Marks finished steps ✅ and the next step 🔄 in the step indicator row
- Updates the status banner with the last completed node name

After the loop, `render_results(final_state)` displays all agent results.
