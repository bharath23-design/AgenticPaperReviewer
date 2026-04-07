"""
Base agent — wraps ChatOllama with token-safe invocation and JSON parsing.
All specialized agents inherit from this class.
"""

import json
import os
import re
import time
from langchain_ollama import ChatOllama
from ..logger import get_logger


class BaseAgent:
    # ~4 chars per token; leave headroom for system prompt + response
    CHARS_PER_TOKEN = 4
    MAX_INPUT_TOKENS = 12_000  # hard cap per LLM call (well under 16k)

    def __init__(self, model_name: str = None):
        self.model_name = model_name or os.getenv("OLLAMA_MODEL", "llama3.2")
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.llm = ChatOllama(
            model=self.model_name,
            base_url=base_url,
            temperature=0.1,
            format="json",      # constrained decoding: model MUST output valid JSON
            num_predict=2048,   # allow enough output tokens to complete the JSON
        )
        self.log = get_logger(self.__class__.__module__ + "." + self.__class__.__name__)
        self.log.debug("Initialized with model=%s base_url=%s", self.model_name, base_url)

    def truncate(self, text: str, max_tokens: int = None) -> str:
        """Truncate text to stay within the token budget."""
        limit = max_tokens or self.MAX_INPUT_TOKENS
        max_chars = limit * self.CHARS_PER_TOKEN
        if len(text) > max_chars:
            self.log.debug(
                "Truncating text from %d to %d chars (token limit: %d)",
                len(text), max_chars, limit,
            )
            return text[:max_chars] + "\n\n[...content truncated to fit token limit]"
        return text

    def invoke_llm(self, prompt: str) -> str:
        """Send prompt to Ollama and return raw string response."""
        token_estimate = len(prompt) // self.CHARS_PER_TOKEN
        self.log.info(
            "Invoking LLM — model=%s prompt_tokens≈%d",
            self.model_name, token_estimate,
        )
        t0 = time.time()
        response = self.llm.invoke(prompt)
        elapsed = time.time() - t0
        self.log.info(
            "LLM response received — %d chars in %.1fs",
            len(response.content), elapsed,
        )
        return response.content

    def parse_json(self, content: str, defaults: dict) -> dict:
        """
        Try to extract a JSON object from LLM output.
        Falls back to `defaults` with a `raw_response` field if parsing fails.
        """
        content = re.sub(r"```(?:json)?\s*", "", content).strip()
        content = re.sub(r"```\s*$", "", content).strip()

        try:
            result = json.loads(content)
            self.log.debug("JSON parsed successfully (direct)")
            return result
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
                self.log.debug("JSON parsed successfully (extracted block)")
                return result
            except json.JSONDecodeError:
                pass

        self.log.warning("JSON parsing failed — using defaults with raw_response")
        result = dict(defaults)
        result["raw_response"] = content
        return result
