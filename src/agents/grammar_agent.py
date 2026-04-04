"""
Grammar & Language Agent — evaluates writing quality, professional tone,
clarity, and syntactic correctness.
"""

from .base_agent import BaseAgent


class GrammarAgent(BaseAgent):

    def analyze(self, sections: dict) -> dict:
        # Use abstract + introduction (most representative of writing quality)
        abstract     = self.truncate(sections.get("abstract", ""), max_tokens=800)
        introduction = self.truncate(sections.get("introduction", ""), max_tokens=5_000)
        conclusion   = self.truncate(sections.get("conclusion", ""), max_tokens=2_000)

        sample_text = f"{abstract}\n\n{introduction}\n\n{conclusion}"
        sample_text = self.truncate(sample_text, max_tokens=8_000)

        prompt = f"""You are an expert academic editor and linguist.

Evaluate the following research paper excerpt for grammar, language quality, and professional academic tone.

---
TEXT SAMPLE:
{sample_text}

---
Assess the following dimensions:
1. Grammar correctness (subject-verb agreement, tense consistency, punctuation)
2. Clarity and readability (sentence structure, flow, coherence)
3. Academic tone (formal register, appropriate hedging, avoidance of colloquialisms)
4. Technical precision (accurate use of domain terminology)

Respond with ONLY a valid JSON object (no markdown, no extra text):
{{
  "rating": "<High | Medium | Low>",
  "grammar_score": <integer 0-100>,
  "clarity_score": <integer 0-100>,
  "tone_score": <integer 0-100>,
  "issues": [<list of specific grammar/language issues found, max 5>],
  "positive_aspects": [<list of writing strengths, max 3>],
  "explanation": "<2-3 sentence overall assessment>"
}}"""

        content = self.invoke_llm(prompt)
        defaults = {
            "rating": "Medium",
            "grammar_score": 70,
            "clarity_score": 70,
            "tone_score": 70,
            "issues": [],
            "positive_aspects": [],
            "explanation": content[:500],
        }
        result = self.parse_json(content, defaults)

        # Validate rating
        valid_ratings = {"High", "Medium", "Low"}
        if result.get("rating") not in valid_ratings:
            # Derive from grammar_score
            score = result.get("grammar_score", 70)
            result["rating"] = "High" if score >= 75 else ("Medium" if score >= 50 else "Low")

        for field in ("grammar_score", "clarity_score", "tone_score"):
            try:
                result[field] = max(0, min(100, int(result[field])))
            except (TypeError, ValueError):
                result[field] = 70

        return result
