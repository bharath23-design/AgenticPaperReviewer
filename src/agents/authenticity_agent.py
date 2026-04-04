"""
Authenticity Agent — estimates the "Fabrication Probability" of the paper
by detecting statistical anomalies, logical leaps, missing details,
and signs of hallucinated or cherry-picked results.
"""

from .base_agent import BaseAgent

class AuthenticityAgent(BaseAgent):

    def analyze(self, sections: dict, metadata: dict) -> dict:
        title       = metadata.get("title", "")
        abstract    = self.truncate(sections.get("abstract", ""), max_tokens=600)
        methodology = self.truncate(sections.get("methodology", ""), max_tokens=3_500)
        results     = self.truncate(sections.get("results", ""), max_tokens=3_500)
        conclusion  = self.truncate(sections.get("conclusion", ""), max_tokens=1_000)

        combined = f"Title: {title}\n\n{abstract}\n\n{methodology}\n\n{results}\n\n{conclusion}"
        combined = self.truncate(combined, max_tokens=9_000)

        prompt = f"""You are an expert research integrity auditor with experience in detecting fabricated or misleading scientific work.

Analyze the following research paper for signs of fabrication, data manipulation, or misleading claims.

Red flags to look for:
1. Results that are suspiciously perfect or too clean (e.g., round numbers, zero variance)
2. Missing methodological details that prevent reproducibility
3. Logical leaps where conclusions exceed what data supports
4. Internal contradictions between sections
5. Implausible performance improvements over baselines (e.g., >50% gains with trivial changes)
6. Vague or non-specific claims about "significant" improvements without statistics
7. Missing ablation studies or sensitivity analyses in ML/AI papers
8. References that seem misused or misrepresented

---
PAPER CONTENT:
{combined}

---
Based on your analysis, estimate the fabrication probability and overall authenticity.

Respond with ONLY a valid JSON object (no markdown, no extra text):
{{
  "fabrication_probability": <integer 0-100, where 0 = almost certainly authentic, 100 = almost certainly fabricated>,
  "risk_level": "<Low | Medium | High | Critical>",
  "red_flags": [
    {{"flag": "<description of anomaly>", "severity": "<minor|moderate|major>"}}
  ],
  "positive_indicators": [<list of signs that support authenticity, max 4>],
  "reproducibility_score": <integer 0-100, where 100 = fully reproducible>,
  "explanation": "<2-3 sentence integrity assessment>",
  "recommendation": "<Accept | Minor Revision | Major Revision | Reject>"
}}"""

        content = self.invoke_llm(prompt)
        defaults = {
            "fabrication_probability": 20,
            "risk_level": "Low",
            "red_flags": [],
            "positive_indicators": [],
            "reproducibility_score": 70,
            "explanation": content[:500],
            "recommendation": "Minor Revision",
        }
        result = self.parse_json(content, defaults)

        # Clamp numeric fields
        for field in ("fabrication_probability", "reproducibility_score"):
            try:
                result[field] = max(0, min(100, int(result[field])))
            except (TypeError, ValueError):
                result[field] = defaults[field]

        # Validate risk level
        valid_risks = {"Low", "Medium", "High", "Critical"}
        if result.get("risk_level") not in valid_risks:
            prob = result.get("fabrication_probability", 20)
            result["risk_level"] = (
                "Critical" if prob >= 75 else
                "High"     if prob >= 50 else
                "Medium"   if prob >= 25 else
                "Low"
            )

        # Validate recommendation
        valid_recs = {"Accept", "Minor Revision", "Major Revision", "Reject"}
        if result.get("recommendation") not in valid_recs:
            result["recommendation"] = "Minor Revision"

        return result
