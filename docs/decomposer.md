# `src/decomposer.py` — Paper Section Decomposer

## Purpose

Splits raw paper text into canonical sections used by the analysis agents:
`abstract`, `introduction`, `related_work`, `methodology`, `experiments`, `results`, `discussion`, `conclusion`.

## Imports

| Import | Used for |
|--------|----------|
| `json` | Parsing JSON from LLM fallback response |
| `re` | Building and applying section-header regex |
| `typing.Dict` | Type annotation for section dictionaries |
| `.logger.get_logger` | Structured logging |

## Public API

### `decompose_paper(full_text: str, abstract: str, llm=None) -> Dict[str, str]`

Returns a dict keyed by canonical section name. Any section not found defaults to `""`.

Always injects the `abstract` from the arXiv API directly (more reliable than regex detection).

Falls back to `_llm_decompose` when fewer than 3 meaningful sections are detected by regex and an `llm` object is provided.

## Strategy

### 1. Regex decomposition (`_regex_decompose`)

- Builds a single combined regex from `SECTION_PATTERNS` that matches common section header lines (case-insensitive, whole-line).
- Splits text at each detected header; maps each match to a canonical name via `_detect_canonical`.
- When a section appears multiple times, keeps the longest occurrence.

### 2. LLM fallback (`_llm_decompose`)

Triggered when regex finds < 3 sections and an `llm` is passed. Sends a truncated version of the paper (≤ 40,000 chars ≈ 10k tokens) to the LLM asking for a JSON object with the five key sections.

### 3. Safety defaults

After both strategies, any missing key in `("abstract", "introduction", "methodology", "results", "conclusion")` is set to `""`. If `methodology` is still empty, the full text (truncated to 20,000 chars) is used as a fallback.

## Section Patterns

```python
SECTION_PATTERNS = [
    ("abstract",     ["abstract"]),
    ("introduction", ["introduction", "1. introduction"]),
    ("related_work", ["related work", "literature review", "background"]),
    ("methodology",  ["methodology", "method", "approach", "architecture", ...]),
    ("experiments",  ["experiment", "setup", "implementation"]),
    ("results",      ["results", "findings", "evaluation", "performance", ...]),
    ("discussion",   ["discussion", "analysis", "ablation"]),
    ("conclusion",   ["conclusion", "summary", "future work"]),
]
```
