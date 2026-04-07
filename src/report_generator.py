"""
Report Generator — converts the final ReviewState into a formatted
Markdown "Judgement Report" suitable for download or display.
"""

from __future__ import annotations
from datetime import date
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from .graph import ReviewState


def _score_bar(score: int, width: int = 20) -> str:
    """Return a simple ASCII progress bar for a 0-100 score."""
    filled = round(score * width / 100)
    return f"[{'█' * filled}{'░' * (width - filled)}] {score}/100"


def _overall_verdict(state: "ReviewState") -> tuple[str, str, int]:
    """
    Derive an overall PASS / CONDITIONAL PASS / FAIL verdict from agent scores.
    Returns (verdict_label, verdict_explanation).
    """
    c  = state.get("consistency_result",   {})
    g  = state.get("grammar_result",       {})
    n  = state.get("novelty_result",       {})
    f  = state.get("fact_check_result",    {})
    a  = state.get("authenticity_result",  {})

    consistency_score  = c.get("score",                   50)
    grammar_score      = g.get("grammar_score",           70)
    novelty_score      = n.get("novelty_score",           60)
    fact_score         = f.get("fact_check_score",        70)
    fabrication_prob   = a.get("fabrication_probability", 20)
    recommendation     = a.get("recommendation",          "Minor Revision")

    # Weighted composite (fabrication is an inverse metric)
    composite = (
        consistency_score * 0.25
        + grammar_score   * 0.10
        + novelty_score   * 0.20
        + fact_score      * 0.20
        + (100 - fabrication_prob) * 0.25
    )

    if composite >= 70 and recommendation in ("Accept", "Minor Revision"):
        verdict = "PASS"
        color_hint = "green"
        explanation = (
            f"The paper meets the minimum quality bar (composite score: {composite:.1f}/100). "
            f"Recommendation: {recommendation}."
        )
    elif composite >= 50:
        verdict = "CONDITIONAL PASS"
        color_hint = "orange"
        explanation = (
            f"The paper has significant strengths but requires revisions "
            f"(composite score: {composite:.1f}/100). Recommendation: {recommendation}."
        )
    else:
        verdict = "FAIL"
        color_hint = "red"
        explanation = (
            f"The paper does not meet the quality bar (composite score: {composite:.1f}/100). "
            f"Recommendation: {recommendation}."
        )

    return verdict, explanation, round(composite)


def _safe_explanation(result: dict, fallback: str = "_Analysis unavailable — model response could not be parsed._") -> str:
    """Return the explanation string, or a clean fallback if JSON parsing failed."""
    if "raw_response" in result:
        return fallback
    return result.get("explanation", fallback)


def generate_report(state: "ReviewState") -> str:
    """Generate a Markdown Judgement Report from the review state."""
    meta  = state.get("paper_metadata", {})
    c     = state.get("consistency_result",  {})
    g     = state.get("grammar_result",      {})
    n     = state.get("novelty_result",      {})
    f     = state.get("fact_check_result",   {})
    a     = state.get("authenticity_result", {})

    verdict, verdict_explanation, composite = _overall_verdict(state)
    today = date.today().isoformat()

    lines = []

    # -----------------------------------------------------------------------
    # Header
    # -----------------------------------------------------------------------
    lines += [
        "# Agentic Paper Review — Judgement Report",
        "",
        f"**Generated:** {today}  ",
        f"**arXiv ID:** {meta.get('arxiv_id', 'N/A')}  ",
        f"**Reviewed URL:** {state.get('url', '')}  ",
        "",
        "---",
        "",
    ]

    # -----------------------------------------------------------------------
    # Paper Metadata
    # -----------------------------------------------------------------------
    authors = ", ".join(meta.get("authors", [])[:5])
    if len(meta.get("authors", [])) > 5:
        authors += " et al."

    lines += [
        "## Paper Metadata",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| **Title** | {meta.get('title', 'N/A')} |",
        f"| **Authors** | {authors} |",
        f"| **Published** | {meta.get('published', 'N/A')} |",
        f"| **Categories** | {', '.join(meta.get('categories', []))} |",
        f"| **DOI** | {meta.get('doi', 'N/A')} |",
        "",
        "---",
        "",
    ]

    # -----------------------------------------------------------------------
    # Executive Summary
    # -----------------------------------------------------------------------
    lines += [
        "## Executive Summary",
        "",
        f"### Overall Verdict: `{verdict}`",
        "",
        f"> {verdict_explanation}",
        "",
        f"**Composite Score:** {_score_bar(composite)}",
        "",
        "| Dimension | Score |",
        "|-----------|-------|",
        f"| Consistency | {c.get('score', 'N/A')}/100 |",
        f"| Grammar | {g.get('grammar_score', 'N/A')}/100 |",
        f"| Novelty | {n.get('novelty_score', 'N/A')}/100 |",
        f"| Fact-Check | {f.get('fact_check_score', 'N/A')}/100 |",
        f"| Authenticity (Integrity) | {100 - a.get('fabrication_probability', 20)}/100 |",
        f"| **Composite** | **{composite}/100** |",
        "",
        "---",
        "",
    ]

    # -----------------------------------------------------------------------
    # 1. Consistency Analysis
    # -----------------------------------------------------------------------
    lines += [
        "## 1. Consistency Analysis",
        "",
        f"**Score:** {_score_bar(c.get('score', 50))}  ",
        f"**Verdict:** `{c.get('verdict', 'N/A')}`",
        "",
        _safe_explanation(c),
        "",
    ]

    if c.get("strengths"):
        lines += ["**Strengths:**", ""]
        for s in c["strengths"]:
            lines.append(f"- {s}")
        lines.append("")

    if c.get("issues"):
        lines += ["**Issues Found:**", ""]
        for issue in c["issues"]:
            lines.append(f"- {issue}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # -----------------------------------------------------------------------
    # 2. Grammar & Language
    # -----------------------------------------------------------------------
    lines += [
        "## 2. Grammar & Language Quality",
        "",
        f"**Overall Rating:** `{g.get('rating', 'N/A')}`  ",
        f"**Grammar Score:** {_score_bar(g.get('grammar_score', 70))}  ",
        f"**Clarity Score:** {_score_bar(g.get('clarity_score', 70))}  ",
        f"**Academic Tone:** {_score_bar(g.get('tone_score', 70))}",
        "",
        _safe_explanation(g),
        "",
    ]

    if g.get("issues"):
        lines += ["**Language Issues:**", ""]
        for issue in g["issues"]:
            lines.append(f"- {issue}")
        lines.append("")

    if g.get("positive_aspects"):
        lines += ["**Positive Aspects:**", ""]
        for aspect in g["positive_aspects"]:
            lines.append(f"- {aspect}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # -----------------------------------------------------------------------
    # 3. Novelty Index
    # -----------------------------------------------------------------------
    related_meta = n.get("related_papers_metadata", [])

    lines += [
        "## 3. Novelty Assessment",
        "",
        f"**Novelty Index:** `{n.get('novelty_index', 'N/A')}`  ",
        f"**Novelty Score:** {_score_bar(n.get('novelty_score', 60))}",
        "",
        _safe_explanation(n),
        "",
    ]

    if n.get("key_differentiators"):
        lines += ["**Key Differentiators:**", ""]
        for d in n["key_differentiators"]:
            lines.append(f"- {d}")
        lines.append("")

    if related_meta:
        lines += ["**Related Papers Found on arXiv:**", ""]
        for p in related_meta[:6]:
            lines.append(
                f"- `{p.get('arxiv_id', '')}` — *{p.get('title', '')}* ({p.get('published', '')})"
            )
        lines.append("")

    lines.append("---")
    lines.append("")

    # -----------------------------------------------------------------------
    # 4. Fact-Check Log
    # -----------------------------------------------------------------------
    verified     = f.get("verified_claims", [])
    questionable = f.get("questionable_claims", [])
    unverifiable = f.get("unverifiable_claims", [])

    lines += [
        "## 4. Fact-Check Log",
        "",
        f"**Fact-Check Score:** {_score_bar(f.get('fact_check_score', 70))}  ",
        f"**Total Claims Examined:** {f.get('total_claims_checked', 0)}",
        "",
        _safe_explanation(f, f.get("summary", "_No summary provided._")),
        "",
    ]

    if verified:
        lines += ["### Verified Claims", ""]
        for item in verified:
            lines.append(f"- **[VERIFIED]** {item.get('claim', '')} — _{item.get('note', '')}_")
        lines.append("")

    if questionable:
        lines += ["### Questionable Claims", ""]
        for item in questionable:
            lines.append(f"- **[QUESTIONABLE]** {item.get('claim', '')} — _{item.get('note', '')}_")
        lines.append("")

    if unverifiable:
        lines += ["### Unverifiable Claims", ""]
        for item in unverifiable:
            lines.append(f"- **[UNVERIFIABLE]** {item.get('claim', '')} — _{item.get('note', '')}_")
        lines.append("")

    lines.append("---")
    lines.append("")

    # -----------------------------------------------------------------------
    # 5. Authenticity / Fabrication Score
    # -----------------------------------------------------------------------
    fab_prob    = a.get("fabrication_probability", 20)
    repro_score = a.get("reproducibility_score", 70)

    lines += [
        "## 5. Authenticity & Integrity Assessment",
        "",
        f"**Fabrication Probability:** {fab_prob}% risk  ",
        f"**Risk Level:** `{a.get('risk_level', 'N/A')}`  ",
        f"**Reproducibility Score:** {_score_bar(repro_score)}",
        "",
        _safe_explanation(a),
        "",
    ]

    if a.get("red_flags"):
        lines += ["**Red Flags Detected:**", ""]
        for flag in a["red_flags"]:
            severity = flag.get("severity", "minor")
            lines.append(f"- [{severity.upper()}] {flag.get('flag', '')}")
        lines.append("")

    if a.get("positive_indicators"):
        lines += ["**Positive Integrity Indicators:**", ""]
        for indicator in a["positive_indicators"]:
            lines.append(f"- {indicator}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # -----------------------------------------------------------------------
    # Final Recommendation
    # -----------------------------------------------------------------------
    lines += [
        "## Final Recommendation",
        "",
        f"**Decision:** `{a.get('recommendation', 'Minor Revision')}`",
        "",
        f"**Overall Verdict:** `{verdict}`",
        "",
        verdict_explanation,
        "",
        "---",
        "",
        "_Report generated by AgenticPaperReviewer · Powered by LangGraph + Ollama_",
    ]

    return "\n".join(lines)
