# `src/agents/base_agent.py` — BaseAgent

## Purpose

Shared base class for all five specialized review agents. Provides LLM initialization, token-safe text truncation, LLM invocation, and JSON response parsing.

## Imports

| Import | Used for |
|--------|----------|
| `json` | Parsing LLM JSON responses |
| `os` | Reading `OLLAMA_MODEL` and `OLLAMA_BASE_URL` env vars |
| `re` | Stripping markdown code fences from LLM output |
| `time` | Measuring LLM invocation latency |
| `langchain_ollama.ChatOllama` | Local Ollama LLM client |
| `..logger.get_logger` | Per-class structured logger |

## Class: `BaseAgent`

### Constructor `__init__(model_name: str = None)`

Initializes `ChatOllama` with:
- `model`: from arg or `OLLAMA_MODEL` env var (default: `llama3.2`)
- `base_url`: from `OLLAMA_BASE_URL` env var (default: `http://localhost:11434`)
- `temperature=0.1` — near-deterministic output
- `format="json"` — constrained decoding forces valid JSON
- `num_predict=2048` — enough tokens to complete structured JSON responses

### `truncate(text: str, max_tokens: int = None) -> str`

Caps text at `max_tokens * 4` characters (≈ 4 chars/token heuristic). Appends a truncation notice if text is shortened. Default cap: 12,000 tokens.

### `invoke_llm(prompt: str) -> str`

Sends the prompt to Ollama and returns `response.content` as a string. Logs prompt token estimate and response latency.

### `parse_json(content: str, defaults: dict) -> dict`

Attempts to decode a JSON object from the LLM's raw string output in two passes:
1. Direct `json.loads(content)` after stripping ` ```json ``` ` fences.
2. Regex extraction of the first `{...}` block and `json.loads` on it.

Falls back to `defaults | {"raw_response": content}` if both passes fail.

## Constants

| Constant | Value | Purpose |
|----------|-------|---------|
| `CHARS_PER_TOKEN` | 4 | Approximation for truncation math |
| `MAX_INPUT_TOKENS` | 12,000 | Hard cap per LLM call |

## Inheritance

All five agents extend `BaseAgent`:

```
BaseAgent
├── ConsistencyAgent
├── GrammarAgent
├── NoveltyAgent
├── FactCheckAgent
└── AuthenticityAgent
```
