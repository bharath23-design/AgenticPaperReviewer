"""
Novelty Agent — assesses the originality of the paper by searching
arXiv for related work and having the LLM judge uniqueness.
"""

from __future__ import annotations
import arxiv
from .base_agent import BaseAgent
from ..logger import get_logger

_log = get_logger(__name__)


_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "do", "does", "did", "have", "has", "had", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "and", "or", "but", "if", "in", "on", "at", "to", "for", "of", "with",
    "by", "from", "up", "about", "into", "through", "during", "all", "you",
    "we", "it", "its", "this", "that", "these", "those", "not", "no", "nor",
}


def _build_query(title: str, categories: list[str]) -> str:
    """
    Build a meaningful arXiv search query from the paper title and categories.

    Strategy:
    - Strip common stopwords so generic title phrases (e.g. "Is All You Need")
      don't dominate the query.
    - Take up to 6 meaningful title keywords.
    - Append the primary arXiv category (e.g. cs.CL) to bias results toward
      the same research area.
    """
    keywords = [w for w in title.split() if w.lower() not in _STOPWORDS][:6]
    query = " ".join(keywords)
    if categories:
        query += f" cat:{categories[0]}"
    return query


def _search_related_papers(title: str, categories: list[str], max_results: int = 8) -> list[dict]:
    """Search arXiv for papers related to the given title and categories."""
    query = _build_query(title, categories)
    _log.debug("arXiv related-paper query: %s", query)

    client = arxiv.Client()
    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.Relevance,
    )
    results = []
    try:
        for paper in client.results(search):
            results.append({
                "title": paper.title,
                "abstract": paper.summary[:300],
                "published": str(paper.published.date()),
                "arxiv_id": paper.entry_id.split("/")[-1],
            })
    except Exception as e:
        _log.warning("arXiv related-paper search failed — %s", e)
    return results


class NoveltyAgent(BaseAgent):

    def analyze(self, sections: dict, metadata: dict) -> dict:
        title      = metadata.get("title", "")
        categories = metadata.get("categories", [])
        abstract   = self.truncate(sections.get("abstract", ""), max_tokens=600)
        conclusion = self.truncate(sections.get("conclusion", ""), max_tokens=1_000)

        # Search for related work (no LLM cost)
        related_papers = _search_related_papers(title, categories, max_results=6)

        related_summary = "\n".join(
            f"- [{p['arxiv_id']}] {p['title']} ({p['published']}): {p['abstract']}"
            for p in related_papers
        )
        related_summary = self.truncate(related_summary, max_tokens=4_000)

        prompt = f"""You are an expert academic reviewer assessing the novelty and originality of a research paper.

PAPER TITLE: {title}

ABSTRACT:
{abstract}

CONCLUSION:
{conclusion}

---
RELATED PAPERS FOUND ON arXiv:
{related_summary if related_summary else "No related papers found (search returned empty)."}

---
Based on the paper's abstract, conclusion, and the related work above, assess its novelty:

1. Does this paper introduce genuinely new ideas, methods, or findings?
2. How does it differ from or improve upon the related work?
3. Is the claimed contribution incremental or substantial?

Respond with ONLY a valid JSON object (no markdown, no extra text):
{{
  "novelty_index": "<Highly Novel | Moderately Novel | Incremental | Derivative>",
  "novelty_score": <integer 0-100, where 100 = groundbreaking>,
  "related_papers": [<list of arXiv IDs from the provided related papers>],
  "key_differentiators": [<list of what makes this paper unique, max 4 items>],
  "overlapping_works": [<list of papers it closely resembles, use their arXiv IDs>],
  "explanation": "<2-3 sentence assessment of novelty>"
}}"""

        content = self.invoke_llm(prompt)
        defaults = {
            "novelty_index": "Moderately Novel",
            "novelty_score": 60,
            "related_papers": [p["arxiv_id"] for p in related_papers],
            "key_differentiators": [],
            "overlapping_works": [],
            "explanation": content[:500],
        }
        result = self.parse_json(content, defaults)

        # Attach full related paper metadata for the report
        result["related_papers_metadata"] = related_papers

        try:
            result["novelty_score"] = max(0, min(100, int(result["novelty_score"])))
        except (TypeError, ValueError):
            result["novelty_score"] = 60

        return result
