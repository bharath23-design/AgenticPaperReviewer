# `src/report_generator.py` — Markdown Report Generator

## Purpose

Converts the completed `ReviewState` into a human-readable Markdown "Judgement Report" that can be downloaded from the UI or saved to disk.

## Imports

| Import | Used for |
|--------|----------|
| `from __future__ import annotations` | Postponed type hint evaluation |
| `datetime.date` | Stamp report with today's date |
| `typing.TYPE_CHECKING` | Guard-import `ReviewState` (avoids circular import) |
| `typing.Any`, `typing.Dict` | Type annotations |

## Public API

### `generate_report(state: "ReviewState") -> str`

Main entry point. Reads all agent results from `state` and produces a multi-section Markdown string.

Sections in order:
1. Header (arXiv ID, URL, generation date)
2. Paper Metadata table (title, authors, published, categories, DOI)
3. Executive Summary (overall verdict, composite score table)
4. Consistency Analysis
5. Grammar & Language Quality
6. Novelty Assessment
7. Fact-Check Log (verified / questionable / unverifiable claims)
8. Authenticity & Integrity Assessment
9. Final Recommendation

## Internal Helpers

### `_score_bar(score: int, width: int = 20) -> str`
Renders a 20-character ASCII progress bar, e.g.:
```
[████████████░░░░░░░░] 60/100
```

### `_overall_verdict(state) -> tuple[str, str, int]`
Computes the weighted composite score and derives a verdict:

| Dimension | Weight |
|-----------|--------|
| Consistency | 25% |
| Grammar | 10% |
| Novelty | 20% |
| Fact-Check | 20% |
| Authenticity (100 − fabrication_probability) | 25% |

Thresholds:
- composite ≥ 70 + recommendation in (Accept, Minor Revision) → **PASS**
- composite ≥ 50 → **CONDITIONAL PASS**
- composite < 50 → **FAIL**

### `_safe_explanation(result, fallback) -> str`
Returns `result["explanation"]` unless the agent fell back to defaults (detected by presence of `"raw_response"` key), in which case returns the fallback message.
