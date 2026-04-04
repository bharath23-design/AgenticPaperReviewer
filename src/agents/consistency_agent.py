"""
Consistency Agent — checks whether the methodology actually supports
the claimed results and conclusions.
"""

from .base_agent import BaseAgent


class ConsistencyAgent(BaseAgent):

    def analyze(self, sections: dict) -> dict:
        abstract    = self.truncate(sections.get("abstract", ""), max_tokens=800)
        methodology = self.truncate(sections.get("methodology", ""), max_tokens=5_000)
        results     = self.truncate(sections.get("results", ""), max_tokens=4_000)
        conclusion  = self.truncate(sections.get("conclusion", ""), max_tokens=1_500)

        prompt = f"""You are an expert scientific peer reviewer specializing in research methodology.

Your task: evaluate whether the METHODOLOGY logically supports the RESULTS and CONCLUSIONS claimed in this paper.

---
ABSTRACT:
{abstract}

---
METHODOLOGY:
{methodology}

---
RESULTS:
{results}

---
CONCLUSION:
{conclusion}

---
Evaluation criteria:
1. Are the experimental setups sufficient to produce the claimed results?
2. Are there logical gaps between what was measured and what was concluded?
3. Are sample sizes, baselines, and comparisons appropriate?
4. Are claims overstated relative to the evidence?

Respond with ONLY a valid JSON object (no markdown, no extra text):
{{
  "score": <integer 0-100, where 100 = perfectly consistent>,
  "verdict": "<Consistent | Partially Consistent | Inconsistent>",
  "strengths": [<list of well-supported claims, max 4 items>],
  "issues": [<list of specific inconsistencies or logical gaps, max 5 items>],
  "explanation": "<2-3 sentence overall assessment>"
}}"""

        content = self.invoke_llm(prompt)
        defaults = {
            "score": 50,
            "verdict": "Partially Consistent",
            "strengths": [],
            "issues": [],
            "explanation": content[:500],
        }
        result = self.parse_json(content, defaults)

        # Clamp score
        try:
            result["score"] = max(0, min(100, int(result["score"])))
        except (TypeError, ValueError):
            result["score"] = 50

        return result
