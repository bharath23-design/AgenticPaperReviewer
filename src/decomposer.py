"""
Paper decomposer — splits raw paper text into canonical sections:
abstract, introduction, methodology, results, discussion, conclusion.

Strategy:
  1. Regex-based section header detection (fast, no LLM cost).
  2. If regex yields poor splits, fall back to LLM-based decomposition
     on a truncated version (≤12 k tokens).
"""

import json
import re
from typing import Dict
from .logger import get_logger

log = get_logger(__name__)


# Ordered list of (canonical_name, list_of_header_patterns)
SECTION_PATTERNS = [
    ("abstract",     [r"\babstract\b"]),
    ("introduction", [r"\bintroduction\b", r"\b1[\.\s]+introduction\b"]),
    ("related_work", [r"\brelated\s+work\b", r"\bliterature\s+review\b", r"\bbackground\b"]),
    ("methodology",  [r"\bmethodolog\w+\b", r"\bmethod\b", r"\bapproach\b",
                      r"\barchitecture\b", r"\bframework\b", r"\bproposed\s+method\b"]),
    ("experiments",  [r"\bexperiment\w*\b", r"\bsetup\b", r"\bimplementation\b"]),
    ("results",      [r"\bresult\w*\b", r"\bfindings\b", r"\bevaluation\b",
                      r"\bperformance\b", r"\bbenchmark\b"]),
    ("discussion",   [r"\bdiscussion\b", r"\banalysis\b", r"\bablation\b"]),
    ("conclusion",   [r"\bconclusion\w*\b", r"\bsummary\b", r"\bfuture\s+work\b"]),
]


def _build_header_regex() -> re.Pattern:
    """Build one big regex that matches any known section header line."""
    all_pats = [p for _, pats in SECTION_PATTERNS for p in pats]
    combined = "|".join(f"(?:{p})" for p in all_pats)
    # Matches a line that IS (mostly) a section header
    return re.compile(
        rf"^(?:\d+[\.\s]*)?\s*(?:{combined})\s*$",
        re.IGNORECASE | re.MULTILINE,
    )


_HEADER_RE = _build_header_regex()


def _detect_canonical(header_text: str) -> str:
    """Map a matched header string to its canonical section name."""
    h = header_text.strip().lower()
    for canonical, pats in SECTION_PATTERNS:
        for pat in pats:
            if re.search(pat, h, re.IGNORECASE):
                return canonical
    return "other"


def _regex_decompose(text: str) -> Dict[str, str]:
    """Split text at detected section headers."""
    splits = []
    for m in _HEADER_RE.finditer(text):
        canonical = _detect_canonical(m.group())
        splits.append((m.start(), m.end(), canonical))

    if not splits:
        log.debug("No section headers detected via regex")
        return {}

    sections: Dict[str, str] = {}
    for i, (start, end, name) in enumerate(splits):
        next_start = splits[i + 1][0] if i + 1 < len(splits) else len(text)
        content = text[end:next_start].strip()
        if content:
            # Keep the longest content if section appears multiple times
            if name not in sections or len(content) > len(sections[name]):
                sections[name] = content

    return sections


def _truncate(text: str, max_chars: int = 48_000) -> str:
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n[...truncated]"
    return text


def _llm_decompose(text: str, llm) -> Dict[str, str]:
    """LLM fallback for papers with non-standard section headings."""
    log.info("Using LLM fallback for section decomposition")
    truncated = _truncate(text, max_chars=40_000)  # ~10k tokens
    prompt = f"""You are a scientific document parser.

Given the following research paper text, extract the content of these sections:
abstract, introduction, methodology, results, conclusion.

For each section return the raw text content.
Respond ONLY with a JSON object like:
{{
  "abstract": "...",
  "introduction": "...",
  "methodology": "...",
  "results": "...",
  "conclusion": "..."
}}

If a section is not present, set its value to an empty string.

PAPER TEXT:
{truncated}
"""
    response = llm.invoke(prompt)
    content = response.content

    # Extract JSON block
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return {}


def decompose_paper(full_text: str, abstract: str, llm=None) -> Dict[str, str]:
    """
    Returns a dict with keys: abstract, introduction, methodology,
    results, discussion, conclusion (any may be empty string if not found).
    """
    log.info("Decomposing paper — input text: %d chars", len(full_text))
    sections = _regex_decompose(full_text)

    sections["abstract"] = abstract

    meaningful = {k: v for k, v in sections.items() if v and len(v) > 100}
    log.info("Regex found %d meaningful sections: %s", len(meaningful), list(meaningful.keys()))

    if len(meaningful) < 3 and llm is not None:
        log.info("Fewer than 3 sections found, invoking LLM fallback")
        llm_sections = _llm_decompose(full_text, llm)
        for key, val in llm_sections.items():
            if val and key not in sections:
                sections[key] = val

    for key in ("abstract", "introduction", "methodology", "results", "conclusion"):
        sections.setdefault(key, "")

    if not sections["methodology"] and full_text:
        log.warning("Methodology section empty, falling back to truncated full text")
        sections["methodology"] = _truncate(full_text, max_chars=20_000)

    log.info(
        "Decomposition complete — sections: %s",
        {k: len(v) for k, v in sections.items() if v},
    )
    return sections
