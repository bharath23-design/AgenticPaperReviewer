# Module Reference

Quick reference for every source file — what it does, what it imports, and its public interface.

---

## `src/logger.py`

**Purpose:** Centralised logging setup. Single source of truth for log format, handlers, and rotation.

### Public API

```python
get_logger(name: str) -> logging.Logger
```

Configures the root logger once (idempotent), then returns a named child logger. Safe to call at module level in any file.

### Internal behaviour
- Creates `logs/` directory if it doesn't exist
- Attaches `TimedRotatingFileHandler` (`logs/app.log`, rotates at midnight, 30 days)
- Attaches `StreamHandler` for console (INFO+ only)
- Silences noisy third-party libraries

---

## `src/scraper.py`

**Purpose:** Fetch paper text and metadata from an arXiv URL.

### Public API

```python
extract_arxiv_id(url: str) -> str
```
Parses arXiv ID from any URL format. Strips version suffix (`v2`). Raises `ValueError` if no ID found.

```python
scrape_paper(url: str) -> dict
```
Main entry point. Returns:
```python
{
    "metadata": {
        "title": str,
        "authors": list[str],
        "abstract": str,
        "published": str,       # "YYYY-MM-DD"
        "arxiv_id": str,
        "categories": list[str],
        "doi": str,
    },
    "full_text": str,           # best available full text
    "abstract": str,            # clean abstract from arXiv API
}
```

### Private helpers
- `_scrape_html_version(arxiv_id)` — fetches `arxiv.org/html/<id>`, parses with BeautifulSoup/lxml
- `_scrape_abstract_page(arxiv_id)` — fetches `arxiv.org/abs/<id>` as fallback
- `_clean_text(text)` — collapses whitespace and normalises line breaks

---

## `src/decomposer.py`

**Purpose:** Split paper text into canonical sections.

### Public API

```python
decompose_paper(full_text: str, abstract: str, llm=None) -> dict[str, str]
```

Returns a dict with keys: `abstract`, `introduction`, `related_work`, `methodology`, `experiments`, `results`, `discussion`, `conclusion`. Any absent section is an empty string.

**Parameters:**
- `full_text` — raw scraped text
- `abstract` — clean abstract from arXiv metadata (always used directly, overrides regex result)
- `llm` — optional `ChatOllama` instance for LLM fallback decomposition

### Constants
- `SECTION_PATTERNS` — ordered list of `(canonical_name, [regex_patterns])` pairs
- `_HEADER_RE` — compiled regex matching any recognised section header line

### Private helpers
- `_regex_decompose(text)` — finds header positions and slices text between them
- `_detect_canonical(header_text)` — maps a matched header to its canonical name
- `_llm_decompose(text, llm)` — LLM fallback, input capped at 40,000 chars
- `_truncate(text, max_chars)` — hard character limit with truncation marker

---

## `src/agents/base_agent.py`

**Purpose:** Base class for all five analysis agents.

### Class: `BaseAgent`

```python
BaseAgent(model_name: str = None)
```

**Class attributes:**
```python
CHARS_PER_TOKEN = 4       # approximation for token counting
MAX_INPUT_TOKENS = 12_000 # hard cap per LLM call
```

**ChatOllama settings:** `temperature=0.1`, `format="json"`, `num_predict=2048`.
- `format="json"` enables Ollama's **constrained decoding** — the model's token sampler is forced at the grammar level to only emit valid JSON. This is more reliable than prompt instructions alone.
- `num_predict=2048` gives the model enough output budget to complete all JSON fields without truncation.

**Methods:**

| Method | Signature | Description |
|--------|-----------|-------------|
| `truncate` | `(text, max_tokens=None) → str` | Trim text to token budget |
| `invoke_llm` | `(prompt) → str` | Call Ollama, log timing |
| `parse_json` | `(content, defaults) → dict` | Extract JSON from LLM output with fallback |

---

## `src/agents/consistency_agent.py`

**Purpose:** Score how well the methodology supports the results.

```python
ConsistencyAgent(model_name=None).analyze(sections: dict) -> dict
```

Output keys: `score` (0-100), `verdict`, `strengths`, `issues`, `explanation`

---

## `src/agents/grammar_agent.py`

**Purpose:** Evaluate writing quality and academic tone.

```python
GrammarAgent(model_name=None).analyze(sections: dict) -> dict
```

Output keys: `rating` (High/Medium/Low), `grammar_score`, `clarity_score`, `tone_score`, `issues`, `positive_aspects`, `explanation`

---

## `src/agents/novelty_agent.py`

**Purpose:** Assess originality using arXiv search + LLM judgment.

```python
NoveltyAgent(model_name=None).analyze(sections: dict, metadata: dict) -> dict
```

Output keys: `novelty_index`, `novelty_score`, `related_papers`, `key_differentiators`, `overlapping_works`, `explanation`, `related_papers_metadata`

**Internal helper:**
```python
_search_related_papers(title, categories, max_results=6) -> list[dict]
```
Uses `arxiv.Client` + `arxiv.Search` — no LLM call, no API cost.

---

## `src/agents/fact_check_agent.py`

**Purpose:** Identify and classify factual claims.

```python
FactCheckAgent(model_name=None).analyze(sections: dict) -> dict
```

Output keys: `verified_claims`, `questionable_claims`, `unverifiable_claims`, `total_claims_checked`, `fact_check_score`, `summary`

---

## `src/agents/authenticity_agent.py`

**Purpose:** Estimate fabrication probability.

```python
AuthenticityAgent(model_name=None).analyze(sections: dict, metadata: dict) -> dict
```

Output keys: `fabrication_probability`, `risk_level`, `red_flags`, `positive_indicators`, `reproducibility_score`, `explanation`, `recommendation`

---

## `src/graph.py`

**Purpose:** LangGraph pipeline that connects all components.

### Public API

```python
create_review_graph() -> CompiledStateGraph
```
Builds and compiles the 8-node `StateGraph`.

```python
run_review(url: str, model_name: str = "llama3.2") -> ReviewState
```
Convenience wrapper: creates graph, builds initial state, invokes, returns final state.

### `ReviewState` (TypedDict)

```python
class ReviewState(TypedDict):
    url:                  str
    model_name:           str
    paper_metadata:       dict
    paper_text:           str
    abstract:             str
    sections:             dict
    consistency_result:   dict
    grammar_result:       dict
    novelty_result:       dict
    fact_check_result:    dict
    authenticity_result:  dict
    final_report:         str
    current_step:         str
    error:                str | None
```

### `_safe_run(node_name, fn, state)`
Wraps every node function. On exception: logs the error and timing, populates `state["error"]`, and lets the graph continue to `END` without crashing.

---

## `src/report_generator.py`

**Purpose:** Convert the final `ReviewState` into a formatted Markdown report.

### Public API

```python
generate_report(state: ReviewState) -> str
```

Returns a multi-section Markdown string. Sections:
1. Header (metadata table)
2. Executive Summary (verdict + composite score table + ASCII score bars)
3. Consistency Analysis
4. Grammar & Language Quality
5. Novelty Assessment
6. Fact-Check Log (verified / questionable / unverifiable)
7. Authenticity & Integrity Assessment
8. Final Recommendation

### Private helpers

```python
_score_bar(score, width=20) -> str    # ASCII progress bar  e.g. [████████░░░░] 42/100
_overall_verdict(state) -> tuple      # (label, explanation, composite_int)
_safe_explanation(result, fallback) -> str  # returns explanation or clean fallback if JSON parse failed (raw_response present)
```

---

## `app.py`

**Purpose:** Streamlit browser UI.

### Key functions

```python
check_ollama(model: str) -> tuple[bool, str]
```
Pre-flight check. Hits `GET <OLLAMA_BASE_URL>/api/tags`, verifies the model is pulled. Returns `(True, "OK")` or `(False, human_readable_reason)`.

```python
_friendly_error(raw: str) -> str
```
Converts a raw Python traceback string into a single human-readable sentence. Special-cases "Connection refused" → Ollama-specific message.

```python
render_results(state: dict)
```
Renders the full result UI: verdict banner, 5 metric cards, 5 detail tabs, download button, report preview.
