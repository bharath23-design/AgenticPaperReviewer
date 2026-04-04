# Agent Reference

All agents live in `src/agents/` and inherit from `BaseAgent`.

---

## BaseAgent (`base_agent.py`)

The foundation class every agent extends. Handles all LLM interaction.

### Constructor
```python
BaseAgent(model_name: str = None)
```
- `model_name` defaults to `OLLAMA_MODEL` env var, then `"llama3.2"`
- Reads `OLLAMA_BASE_URL` (default `http://localhost:11434`)
- Initialises `ChatOllama` with `temperature=0.1`, `format="json"` (Ollama constrained decoding — model is forced at grammar level to emit valid JSON), and `num_predict=2048` (allows enough output tokens to complete the response)
- Initialises a module-scoped logger

### Key Methods

#### `truncate(text, max_tokens=12000) → str`
Trims text to fit within the token budget.
- Approximates 1 token ≈ 4 characters
- Appends `[...content truncated to fit token limit]` if cut
- Call this on every section before building a prompt

#### `invoke_llm(prompt) → str`
Sends the prompt to Ollama and returns the raw text response.
- Logs model name, estimated token count, and elapsed time
- Raises on connection errors (caught by `_safe_run` in graph)

#### `parse_json(content, defaults) → dict`
Extracts a JSON object from the LLM response.
1. Strips markdown code fences (` ```json ... ``` `)
2. Tries `json.loads()` directly
3. Tries regex `\{.*\}` extraction
4. Falls back to `defaults` + `raw_response` key if all else fails

---

## ConsistencyAgent (`consistency_agent.py`)

**Purpose:** Checks whether the methodology logically supports the claimed results and conclusions.

### Input sections
| Section | Token budget |
|---------|-------------|
| abstract | 800 |
| methodology | 5,000 |
| results | 4,000 |
| conclusion | 1,500 |

### Output schema
```json
{
  "score": 88,
  "verdict": "Consistent | Partially Consistent | Inconsistent",
  "strengths": ["list of well-supported claims"],
  "issues": ["list of logical gaps"],
  "explanation": "2-3 sentence assessment"
}
```

### Evaluation criteria
1. Do the experimental setups justify the claimed results?
2. Are there logical leaps between measurements and conclusions?
3. Are baselines and comparisons appropriate?
4. Are claims overstated relative to the evidence?

---

## GrammarAgent (`grammar_agent.py`)

**Purpose:** Evaluates writing quality, academic tone, and syntactic correctness.

### Input sections
| Section | Token budget |
|---------|-------------|
| abstract | 800 |
| introduction | 5,000 |
| conclusion | 2,000 |

### Output schema
```json
{
  "rating": "High | Medium | Low",
  "grammar_score": 91,
  "clarity_score": 88,
  "tone_score": 92,
  "issues": ["list of language problems"],
  "positive_aspects": ["writing strengths"],
  "explanation": "2-3 sentence assessment"
}
```

### Derived rating logic
If the LLM returns an invalid rating string, it is derived from `grammar_score`:
- ≥ 75 → `High`
- 50–74 → `Medium`
- < 50 → `Low`

---

## NoveltyAgent (`novelty_agent.py`)

**Purpose:** Assesses originality by searching arXiv for related work and asking the LLM to judge uniqueness.

### Two-phase process

**Phase 1 — arXiv search (no LLM cost)**
```python
_search_related_papers(title, categories, max_results=6)
```
- Builds a query from the first 8 words of the paper title
- Uses the `arxiv` Python library (`arxiv.Search`)
- Returns up to 6 related papers with title, abstract preview, published date

**Phase 2 — LLM novelty judgment**
- Feeds the paper's abstract + conclusion + related paper summaries to the LLM
- Asks it to assess novelty across three dimensions: newness, differentiation, incremental vs. substantial

### Input sections
| Section | Token budget |
|---------|-------------|
| abstract | 600 |
| conclusion | 1,000 |
| related paper summaries | 4,000 |

### Output schema
```json
{
  "novelty_index": "Highly Novel | Moderately Novel | Incremental | Derivative",
  "novelty_score": 90,
  "related_papers": ["2303.08774", "1810.04805"],
  "key_differentiators": ["what makes this paper unique"],
  "overlapping_works": ["arxiv IDs of close matches"],
  "explanation": "2-3 sentence assessment",
  "related_papers_metadata": [{ "arxiv_id", "title", "abstract", "published" }]
}
```

---

## FactCheckAgent (`fact_check_agent.py`)

**Purpose:** Identifies and classifies factual claims in the paper.

### What it checks
- Mathematical constants and well-known values (π, speed of light, etc.)
- Statistical thresholds (p-values, significance levels)
- Historical facts or dates cited
- Benchmark dataset statistics
- Formulas that can be spot-checked
- Numerical claims that seem unusually high or low

### Input sections
| Section | Token budget |
|---------|-------------|
| abstract | 500 |
| methodology | 4,000 |
| results | 4,000 |
| conclusion | 1,000 |

### Claim classification
| Status | Meaning |
|--------|---------|
| `verified` | Matches known facts / standard in the field |
| `plausible` | Reasonable but needs more context |
| `questionable` | Appears incorrect, overstated, or inconsistent |
| `unverifiable` | Requires domain-specific data not available |

### Output schema
```json
{
  "verified_claims":     [{ "claim": "...", "status": "verified",     "note": "..." }],
  "questionable_claims": [{ "claim": "...", "status": "questionable", "note": "..." }],
  "unverifiable_claims": [{ "claim": "...", "status": "unverifiable", "note": "..." }],
  "total_claims_checked": 8,
  "fact_check_score": 85,
  "summary": "2-3 sentence assessment"
}
```

---

## AuthenticityAgent (`authenticity_agent.py`)

**Purpose:** Estimates the probability that results are fabricated or misleading.

### Red flags it looks for
1. Suspiciously round numbers or zero variance in results
2. Missing methodological details (reproducibility blockers)
3. Logical leaps where conclusions exceed data
4. Internal contradictions between sections
5. Implausible performance improvements (e.g., >50% gain from trivial changes)
6. Vague "significant improvement" claims without statistics
7. Missing ablation studies in ML/AI papers
8. Misrepresented references

### Input sections
| Section | Token budget |
|---------|-------------|
| abstract | 600 |
| methodology | 3,500 |
| results | 3,500 |
| conclusion | 1,000 |

### Output schema
```json
{
  "fabrication_probability": 10,
  "risk_level": "Low | Medium | High | Critical",
  "red_flags": [{ "flag": "description", "severity": "minor|moderate|major" }],
  "positive_indicators": ["signs supporting authenticity"],
  "reproducibility_score": 85,
  "explanation": "2-3 sentence integrity assessment",
  "recommendation": "Accept | Minor Revision | Major Revision | Reject"
}
```

### Risk level derivation
If the LLM returns an invalid `risk_level`, it is derived from `fabrication_probability`:
| Probability | Risk Level |
|-------------|-----------|
| 0–24% | `Low` |
| 25–49% | `Medium` |
| 50–74% | `High` |
| 75–100% | `Critical` |
