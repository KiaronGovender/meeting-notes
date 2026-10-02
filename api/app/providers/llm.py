import json
import time
from typing import Protocol

import httpx

from ..config import settings


class LLMClient(Protocol):
    def complete_json(self, system: str, user: str) -> dict: ...


def _parse(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        return json.loads(text[start : end + 1])


class OllamaClient:
    """Local development."""

    def complete_json(self, system: str, user: str) -> dict:
        r = httpx.post(
            f"{settings.ollama_url}/api/chat",
            json={
                "model": settings.ollama_model,
                "stream": False,
                "format": "json",
                "options": {"num_ctx": 8192, "temperature": 0.2},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            },
            timeout=600,
        )
        r.raise_for_status()
        return _parse(r.json()["message"]["content"])


class OpenAICompatClient:
    """Any OpenAI-compatible API: Groq, Gemini, OpenRouter... Retries on free-tier rate limits."""

    def complete_json(self, system: str, user: str) -> dict:
        for attempt in range(6):
            r = httpx.post(
                f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json={
                    "model": settings.llm_model,
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"},
                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                },
                timeout=120,
            )
            if r.status_code in (429, 503):
                try:
                    wait = float(r.headers.get("retry-after", ""))
                except ValueError:
                    wait = min(3 * 2**attempt, 30)
                time.sleep(min(wait, 60))
                continue
            r.raise_for_status()
            return _parse(r.json()["choices"][0]["message"]["content"])
        raise RuntimeError("LLM rate limit: retries exhausted")


def get_llm() -> LLMClient:
    if settings.llm_provider == "ollama":
        return OllamaClient()
    if settings.llm_provider == "openai":
        return OpenAICompatClient()
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.llm_provider}")