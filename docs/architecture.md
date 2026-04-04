# System Architecture

## Overview

The Agentic Research Paper Evaluator is a **multi-agent pipeline** that takes an arXiv URL and produces a peer-review-quality Judgement Report. It is built on three pillars:

| Pillar | Technology | Role |
|--------|-----------|------|
| Orchestration | LangGraph `StateGraph` | Connects all nodes in a directed acyclic graph |
| LLM Inference | Ollama (local) | Runs open-source models with zero API cost |
| Interface | Streamlit | Browser UI with real-time step tracking |

---

## High-Level Data Flow

```
User pastes arXiv URL
        │
        ▼
┌───────────────────┐
│   app.py          │  Streamlit UI — input, progress, results, download
│   (Ollama check)  │  Pre-flight: confirms Ollama is reachable + model pulled
└────────┬──────────┘
         │  url + model_name
         ▼
┌───────────────────┐
│   graph.py        │  LangGraph StateGraph — compiles & streams the pipeline
│   ReviewState     │  Shared typed dict passed through all nodes
└────────┬──────────┘
         │
    ┌────┴─────────────────────────────────────────────────┐
    │                   8-Node Pipeline                    │
    │                                                      │
    │  [1] scrape ──► [2] decompose ──► [3] consistency   │
    │                                       │              │
    │                                  [4] grammar         │
    │                                       │              │
    │                                  [5] novelty         │
    │                                       │              │
    │                                  [6] fact_check      │
    │                                       │              │
    │                                  [7] authenticity    │
    │                                       │              │
    │                                  [8] report ──► END  │
    └──────────────────────────────────────────────────────┘
         │
         ▼
   Markdown Judgement Report
   (displayed in UI + downloadable)
```

---

## Component Breakdown

### 1. Scraper (`src/scraper.py`)

**Responsibility:** Fetch clean text and metadata from arXiv.

**Strategy (waterfall):**
```
arXiv Metadata API (via arxiv library)
    → HTML full-text version  (arxiv.org/html/<id>)
    → Abstract page fallback  (arxiv.org/abs/<id>)
    → Raw abstract (last resort)
```

**Output fields:**
```python
{
    "metadata": { title, authors, published, arxiv_id, categories, doi },
    "full_text": str,   # best available text, up to 100k+ chars
    "abstract":  str,   # clean abstract from arXiv API
}
```

---

### 2. Decomposer (`src/decomposer.py`)

**Responsibility:** Split raw paper text into canonical sections.

**Strategy:**
1. **Regex scan** — looks for section headers matching known patterns (Abstract, Introduction, Methodology, Results, Discussion, Conclusion, etc.)
2. **LLM fallback** — if fewer than 3 sections are found by regex, sends the first ~10k tokens to the LLM and asks it to extract sections as JSON.

**Output keys:** `abstract`, `introduction`, `related_work`, `methodology`, `experiments`, `results`, `discussion`, `conclusion`

**Token safety:** LLM fallback input is hard-capped at 40,000 chars (~10k tokens).

---

### 3. Agent Layer (`src/agents/`)

All agents share a common `BaseAgent` class that provides:

- **Token-safe truncation** — each section is truncated before being included in a prompt
- **Constrained JSON output** — `ChatOllama` is initialised with `format="json"` and `num_predict=2048`. Ollama's grammar sampler forces every generated token to be valid JSON, eliminating truncated or malformed responses
- **LLM invocation with timing** — logs model name, estimated tokens, and response time
- **JSON parsing with fallback** — strips markdown fences, tries direct parse, then regex extraction, then defaults + `raw_response` key

Each agent receives only the sections it needs, keeping every LLM call well under the 16k token limit.

| Agent | File | Input Sections | Max Prompt Tokens |
|-------|------|----------------|-------------------|
| Consistency | `consistency_agent.py` | abstract + methodology + results + conclusion | ~11,300 |
| Grammar | `grammar_agent.py` | abstract + introduction + conclusion | ~8,000 |
| Novelty | `novelty_agent.py` | abstract + conclusion + arXiv search results | ~6,400 |
| Fact-Check | `fact_check_agent.py` | abstract + methodology + results + conclusion | ~9,000 |
| Authenticity | `authenticity_agent.py` | abstract + methodology + results + conclusion | ~9,000 |

---

### 4. LangGraph Orchestration (`src/graph.py`)

**State schema (`ReviewState`):**
```python
class ReviewState(TypedDict):
    url:                  str
    model_name:           str
    paper_metadata:       dict       # from scraper
    paper_text:           str        # from scraper
    abstract:             str        # from scraper
    sections:             dict       # from decomposer
    consistency_result:   dict       # from ConsistencyAgent
    grammar_result:       dict       # from GrammarAgent
    novelty_result:       dict       # from NoveltyAgent
    fact_check_result:    dict       # from FactCheckAgent
    authenticity_result:  dict       # from AuthenticityAgent
    final_report:         str        # from ReportGenerator
    current_step:         str        # progress tracking
    error:                str | None # captured by _safe_run
```

**Error isolation:** Every node is wrapped in `_safe_run()`, which catches all exceptions, logs them with timing, and stores the error in state without crashing the graph.

---

### 5. Report Generator (`src/report_generator.py`)

**Responsibility:** Convert the final `ReviewState` into a formatted Markdown report.

**Composite score formula:**
```
composite = (
    consistency_score  × 0.25
  + grammar_score      × 0.10
  + novelty_score      × 0.20
  + fact_check_score   × 0.20
  + (100 − fabrication_probability) × 0.25
)
```

**Verdict thresholds:**
| Composite | Verdict |
|-----------|---------|
| ≥ 70 | `PASS` |
| 50–69 | `CONDITIONAL PASS` |
| < 50 | `FAIL` |

**Render helpers:**
- `_score_bar(score)` — renders an ASCII progress bar (e.g. `[████████░░░░] 42/100`)
- `_safe_explanation(result, fallback)` — returns the agent's `explanation` field if JSON parsing succeeded, or a clean italicised fallback message if `raw_response` is present (i.e., parsing failed). Prevents raw JSON blobs from appearing in the report.

---

### 6. Logging Middleware (`src/logger.py`)

**Responsibility:** Provide a unified, daily-rotating log file for all modules.

- Single call `get_logger(__name__)` from any module
- File handler: `DEBUG` and above → `logs/app.log`
- Console handler: `INFO` and above → terminal
- Rotation: midnight, 30-day retention (`logs/app.log.YYYY-MM-DD`)
- Noisy third-party libraries silenced to `WARNING`: `httpx`, `httpcore`, `urllib3`, `requests`, `arxiv`, `langchain`, `langchain_core`, `langchain_ollama`, `langgraph`, `watchdog`, `fsevents`

---

### 7. Streamlit UI (`app.py`)

**Ollama pre-flight check** (before any graph execution):
1. Hits `GET /api/tags` on the Ollama base URL
2. Confirms the selected model is in the pulled model list
3. Shows a clear, actionable error if either check fails — no raw tracebacks

**Progress tracking:** Streams `graph.stream()` and updates the 8-step indicator in real time.

**Error display:** Parses captured tracebacks and shows the human-readable root cause. Full traceback available in an expander.

---

## Token Budget

The assignment requires **< 16,000 tokens per LLM call**. Every agent enforces a hard cap of **12,000 input tokens** (≈ 48,000 characters), leaving ~4,000 tokens of headroom for the system prompt and response.

```
Section truncation  →  per-section limits (800 – 5,000 tokens)
Prompt assembly     →  sum of all sections + prompt template
Hard cap            →  BaseAgent.truncate() at 12,000 tokens
Actual budget used  →  typically 4,000 – 10,000 tokens per agent
```
