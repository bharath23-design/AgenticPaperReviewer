"""
Fact-Check Agent — identifies and verifies factual claims: constants,
formulas, cited statistics, and historical data within the paper.
"""

from .base_agent import BaseAgent


class FactCheckAgent(BaseAgent):

    def analyze(self, sections: dict) -> dict:
        abstract    = self.truncate(sections.get("abstract", ""), max_tokens=500)
        methodology = self.truncate(sections.get("methodology", ""), max_tokens=4_000)
        results     = self.truncate(sections.get("results", ""), max_tokens=4_000)
        conclusion  = self.truncate(sections.get("conclusion", ""), max_tokens=1_000)

        combined = f"{abstract}\n\n{methodology}\n\n{results}\n\n{conclusion}"
        combined = self.truncate(combined, max_tokens=9_000)

        prompt = f"""You are a scientific fact-checker with expertise across multiple research domains.

Review the following research paper content and identify specific factual claims that can be verified or questioned.

Focus on:
- Mathematical constants or well-known values (e.g., π, speed of light, Boltzmann constant)
- Statistical thresholds (e.g., p < 0.05 for significance)
- Historical facts or dates cited
- Benchmark dataset statistics or standard metrics
- Formulas or equations that can be spot-checked
- Any numerical claims that seem unusually high or low

---
PAPER CONTENT:
{combined}

---
For each claim you identify, classify it as:
- "verified": Claim matches known facts / is standard in the field
- "plausible": Claim is reasonable but cannot be confirmed without more context
- "questionable": Claim appears incorrect, overstated, or inconsistent with known facts
- "unverifiable": Claim requires domain-specific data not generally available

Respond with ONLY a valid JSON object (no markdown, no extra text):
{{
  "verified_claims": [
    {{"claim": "<exact claim>", "status": "verified", "note": "<why it's correct>"}}
  ],
  "questionable_claims": [
    {{"claim": "<exact claim>", "status": "questionable", "note": "<why it's suspect>"}}
  ],
  "unverifiable_claims": [
    {{"claim": "<exact claim>", "status": "unverifiable", "note": "<what would be needed>"}}
  ],
  "total_claims_checked": <integer>,
  "fact_check_score": <integer 0-100, 100 = all claims verified>,
  "summary": "<2-3 sentence overall fact-check assessment>"
}}"""

        content = self.invoke_llm(prompt)
        defaults = {
            "verified_claims": [],
            "questionable_claims": [],
            "unverifiable_claims": [],
            "total_claims_checked": 0,
            "fact_check_score": 70,
            "summary": content[:500],
        }
        result = self.parse_json(content, defaults)

        try:
            result["fact_check_score"] = max(0, min(100, int(result["fact_check_score"])))
        except (TypeError, ValueError):
            result["fact_check_score"] = 70

        # Always recompute from actual lists — don't trust the model's count
        result["total_claims_checked"] = (
            len(result.get("verified_claims", []))
            + len(result.get("questionable_claims", []))
            + len(result.get("unverifiable_claims", []))
        )

        return result
