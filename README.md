# Agentic Research Paper Evaluator

A multi-agent system that autonomously reviews arXiv research papers using **LangGraph** and **Ollama** (local, free-tier LLMs). It simulates a peer-review panel by running 5 specialized agents and produces a structured **Judgement Report**.

---

## Architecture

```
User pastes arXiv URL
         │
         ▼
┌─────────────────────┐
│      app.py         │  Streamlit UI
│  (Ollama pre-flight)│  Checks Ollama + model before starting
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│     graph.py        │  LangGraph StateGraph
│   (ReviewState)     │  Shared typed dict through all 8 nodes
└────────┬────────────┘
         │
         ▼
   ┌─────────────┐
   │  [1] scrape │  src/scraper.py
   │             │  arXiv HTML → abstract page → raw abstract
   └──────┬──────┘
          │
   ┌──────▼──────┐
   │ [2] decompose│  src/decomposer.py
   │             │  Regex split → LLM fallback
   └──────┬──────┘
          │
   ┌──────▼──────────────────────────────────────────┐
   │                  Agent Layer                    │
   │  [3] consistency  src/agents/consistency_agent  │
   │  [4] grammar      src/agents/grammar_agent      │
   │  [5] novelty      src/agents/novelty_agent      │
   │  [6] fact_check   src/agents/fact_check_agent   │
   │  [7] authenticity src/agents/authenticity_agent │
   └──────┬──────────────────────────────────────────┘
          │
   ┌──────▼──────┐
   │  [8] report │  src/report_generator.py
   │             │  Markdown Judgement Report
   └─────────────┘
          │
          ▼
  Download / Preview in UI

        ┌──────────────────┐
        │  src/logger.py   │  Logging middleware (all modules)
        │  logs/app.log    │  Daily rotation, 30-day retention
        └──────────────────┘
```

---

## Agents

| # | Agent | Input Sections | Output |
|---|-------|---------------|--------|
| 1 | **Consistency** | methodology + results + conclusion | Score 0-100, verdict, issues |
| 2 | **Grammar** | abstract + introduction + conclusion | Rating High/Med/Low, 3 sub-scores |
| 3 | **Novelty** | abstract + conclusion + arXiv search | Novelty index, related papers |
| 4 | **Fact-Check** | methodology + results | Verified / Questionable / Unverifiable claims |
| 5 | **Authenticity** | full paper (truncated) | Fabrication %, risk level, red flags |

**Token limit:** Every agent caps its LLM input at **≤ 12,000 tokens** (assignment requires < 16k).

---

## Report Structure

```
# Judgement Report
├── Paper Metadata
├── Executive Summary  →  PASS / CONDITIONAL PASS / FAIL  +  Composite Score
├── 1. Consistency Score       (0-100)
├── 2. Grammar Rating          (High / Medium / Low)
├── 3. Novelty Index           (Highly Novel → Derivative)
├── 4. Fact-Check Log          (verified / questionable / unverifiable)
└── 5. Fabrication Probability (% risk + recommendation)
```

**Composite score formula:**
```
composite = consistency×0.25 + grammar×0.10 + novelty×0.20
          + fact_check×0.20 + (100 − fabrication_prob)×0.25
```

---

## Quick Start

### 1. Install Ollama

Download from **https://ollama.com/download**, then:

```bash
ollama pull llama3.2        # Recommended — fast, 2 GB
ollama pull llama3.1:8b     # Higher quality — 5 GB
ollama pull mistral         # Alternative — 4 GB
ollama pull gemma2:2b       # Lightweight — 1.6 GB
```

### 2. Create Virtual Environment (Python 3.12)

```bash
python3.12 -m venv .venv
source .venv/bin/activate      # macOS / Linux
# .venv\Scripts\activate       # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
# Edit .env if you want a different model or Ollama URL
```

`.env` options:
```
OLLAMA_MODEL=llama3.2
OLLAMA_BASE_URL=http://localhost:11434
```

### 5. Run the App

```bash
streamlit run app.py
```

Open **http://localhost:8501** in your browser.

---

## Usage

1. Paste an arXiv URL — e.g. `https://arxiv.org/pdf/1706.03762`
2. Select your Ollama model in the sidebar
3. Click **Analyze** — the UI runs a pre-flight check first
4. Watch all 8 pipeline steps complete in real time
5. Download the **Markdown Judgement Report**

---

## Logging

All modules write structured logs to `logs/app.log` (daily rotation, 30-day retention).

```
logs/
├── app.log              ← today's active file
├── app.log.2026-04-03   ← yesterday's (auto-rotated)
└── ...
```

Format: `YYYY-MM-DD HH:MM:SS | LEVEL | module | message`

The `logs/` folder is git-ignored — never pushed to the repo.
See [docs/logging.md](docs/logging.md) for full details.

---

## Project Structure

```
AgenticPaperReviewer/
├── app.py                        # Streamlit UI + Ollama pre-flight
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
│
├── src/
│   ├── logger.py                 # Centralised logging (daily rotation)
│   ├── scraper.py                # arXiv web scraper (HTML → abstract fallback)
│   ├── decomposer.py             # Section splitter (regex → LLM fallback)
│   ├── graph.py                  # LangGraph 8-node pipeline + ReviewState
│   ├── report_generator.py       # Markdown Judgement Report builder
│   └── agents/
│       ├── base_agent.py         # Token safety, constrained JSON output (format="json"), LLM invocation
│       ├── consistency_agent.py  # Methodology vs Results (score 0-100)
│       ├── grammar_agent.py      # Grammar / Clarity / Tone (High/Med/Low)
│       ├── novelty_agent.py      # arXiv search + LLM novelty judgment
│       ├── fact_check_agent.py   # Verified / Questionable / Unverifiable claims
│       └── authenticity_agent.py # Fabrication probability %
│
├── docs/
│   ├── architecture.md           # System design + data flow
│   ├── agents.md                 # Per-agent input/output reference
│   ├── logging.md                # Logging system documentation
│   └── modules.md                # Full module API reference
│
└── logs/                         # Git-ignored — auto-created at runtime
    └── app.log                   # Today's log (rotates at midnight)
```

---

## Running as a Script (no UI)

```python
from src.graph import run_review

state = run_review(
    url="https://arxiv.org/pdf/1706.03762",
    model_name="llama3.2",
)
print(state["final_report"])
```

---

## Documentation

| Doc | Contents |
|-----|----------|
| [docs/architecture.md](docs/architecture.md) | System design, data flow, component breakdown |
| [docs/agents.md](docs/agents.md) | Input/output schema and prompt logic for each agent |
| [docs/logging.md](docs/logging.md) | Log levels, format, rotation, what each module logs |
| [docs/modules.md](docs/modules.md) | Full public API reference for every source file |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Ollama not ready` in UI | Open the Ollama app or run `ollama serve` in a terminal |
| Model not found | Run `ollama pull <model-name>` |
| Slow analysis | Use `llama3.2:1b` or `gemma2:2b` for faster responses |
| arXiv HTML unavailable | Older papers fall back to abstract-only automatically |
| JSON parse errors | Resolved by Ollama's `format="json"` constrained decoding — model is forced to emit valid JSON. Defaults still apply as a safety net if parsing fails |
| Check logs for details | `cat logs/app.log` or `tail -f logs/app.log` |
