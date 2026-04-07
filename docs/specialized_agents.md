# Specialized Agents

All agents inherit from `BaseAgent` and expose a single `analyze(...)` method that returns a validated dict.

---

## `ConsistencyAgent` (`src/agents/consistency_agent.py`)

### Imports
| Import | Used for |
|--------|----------|
| `.base_agent.BaseAgent` | Shared LLM + JSON utilities |

### `analyze(sections: dict) -> dict`

Checks whether the methodology logically supports the results and conclusions.

**Input sections used:** `abstract` (800 tok), `methodology` (5,000 tok), `results` (4,000 tok), `conclusion` (1,500 tok)

**Output keys:**

| Key | Type | Description |
|-----|------|-------------|
| `score` | int 0–100 | 100 = perfectly consistent |
| `verdict` | str | `Consistent` / `Partially Consistent` / `Inconsistent` |
| `strengths` | list[str] | Well-supported claims (max 4) |
| `issues` | list[str] | Logical gaps (max 5) |
| `explanation` | str | 2–3 sentence summary |

Score is clamped to `[0, 100]`.

---

## `GrammarAgent` (`src/agents/grammar_agent.py`)

### Imports
| Import | Used for |
|--------|----------|
| `.base_agent.BaseAgent` | Shared LLM + JSON utilities |

### `analyze(sections: dict) -> dict`

Evaluates writing quality, clarity, academic tone, and technical precision.

**Input sections used:** `abstract` (800 tok) + `introduction` (5,000 tok) + `conclusion` (2,000 tok), concatenated and re-truncated to 8,000 tok.

**Output keys:**

| Key | Type | Description |
|-----|------|-------------|
| `rating` | str | `High` / `Medium` / `Low` |
| `grammar_score` | int 0–100 | |
| `clarity_score` | int 0–100 | |
| `tone_score` | int 0–100 | |
| `issues` | list[str] | Language issues (max 5) |
| `positive_aspects` | list[str] | Writing strengths (max 3) |
| `explanation` | str | 2–3 sentence summary |

`rating` is derived from `grammar_score` if the LLM returns an invalid value.

---

## `NoveltyAgent` (`src/agents/novelty_agent.py`)

### Imports
| Import | Used for |
|--------|----------|
| `from __future__ import annotations` | Postponed annotation evaluation |
| `arxiv` | arXiv search client for related-paper lookup |
| `.base_agent.BaseAgent` | Shared LLM + JSON utilities |
| `..logger.get_logger` | Module-level logger |

### `analyze(sections: dict, metadata: dict) -> dict`

Searches arXiv for related work (no LLM cost), then asks the LLM to judge uniqueness.

**arXiv search:** uses the first 8 words of the paper title, retrieves up to 6 results sorted by relevance.

**Output keys:**

| Key | Type | Description |
|-----|------|-------------|
| `novelty_index` | str | `Highly Novel` / `Moderately Novel` / `Incremental` / `Derivative` |
| `novelty_score` | int 0–100 | 100 = groundbreaking |
| `related_papers` | list[str] | arXiv IDs of similar work |
| `key_differentiators` | list[str] | What makes this paper unique (max 4) |
| `overlapping_works` | list[str] | arXiv IDs of closely similar papers |
| `explanation` | str | 2–3 sentence assessment |
| `related_papers_metadata` | list[dict] | Full metadata for related papers |

---

## `FactCheckAgent` (`src/agents/fact_check_agent.py`)

### Imports
| Import | Used for |
|--------|----------|
| `.base_agent.BaseAgent` | Shared LLM + JSON utilities |

### `analyze(sections: dict) -> dict`

Identifies and classifies factual claims as verified, questionable, or unverifiable.

**Output keys:**

| Key | Type | Description |
|-----|------|-------------|
| `verified_claims` | list[dict] | `{claim, status, note}` each |
| `questionable_claims` | list[dict] | Same structure |
| `unverifiable_claims` | list[dict] | Same structure |
| `total_claims_checked` | int | Auto-computed if not set by LLM |
| `fact_check_score` | int 0–100 | 100 = all claims verified |
| `summary` | str | 2–3 sentence assessment |

---

## `AuthenticityAgent` (`src/agents/authenticity_agent.py`)

### Imports
| Import | Used for |
|--------|----------|
| `.base_agent.BaseAgent` | Shared LLM + JSON utilities |

### `analyze(sections: dict, metadata: dict) -> dict`

Estimates fabrication probability and overall research integrity.

**Output keys:**

| Key | Type | Description |
|-----|------|-------------|
| `fabrication_probability` | int 0–100 | 0 = authentic, 100 = fabricated |
| `risk_level` | str | `Low` / `Medium` / `High` / `Critical` |
| `red_flags` | list[dict] | `{flag, severity}` each |
| `positive_indicators` | list[str] | Signs supporting authenticity |
| `reproducibility_score` | int 0–100 | |
| `explanation` | str | 2–3 sentence integrity assessment |
| `recommendation` | str | `Accept` / `Minor Revision` / `Major Revision` / `Reject` |

`risk_level` and `recommendation` are validated and corrected if LLM returns out-of-range values.
