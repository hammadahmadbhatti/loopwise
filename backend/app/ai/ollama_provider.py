"""Free, local LLM provider via Ollama (https://ollama.com).

Runs models such as qwen2.5 or llama3 on your own machine: no API key, no cost,
and feedback never leaves your infrastructure. Uses Ollama's structured outputs
(``format`` = JSON schema) through its REST API.
"""

from __future__ import annotations

import time

import httpx

from ..config import get_settings
from .base import ProviderError, T, strict_json_schema
from .llm import LLMProvider

_STATUS_CACHE: dict[str, tuple[float, tuple[bool, str]]] = {}


def ollama_models(base_url: str, client: httpx.Client | None = None) -> list[str] | None:
    """Names of locally pulled models, or None if Ollama isn't reachable."""
    try:
        c = client or httpx.Client(timeout=1.5)
        r = c.get(f"{base_url}/api/tags")
        r.raise_for_status()
        return [m.get("name", "") for m in r.json().get("models", [])]
    except (httpx.HTTPError, ValueError):
        return None


def model_present(wanted: str, installed: list[str]) -> bool:
    base = wanted.split(":")[0]
    return any(m == wanted or m == f"{wanted}:latest" or (":" not in wanted and m.split(":")[0] == base)
               for m in installed)


class OllamaProvider(LLMProvider):
    name = "ollama"

    def __init__(self, client: httpx.Client | None = None, model: str | None = None, base_url: str | None = None):
        settings = get_settings()
        self.model = model or settings.ollama_model
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self._client = client

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=300.0)
        return self._client

    def available(self) -> tuple[bool, str]:
        key = f"{self.base_url}|{self.model}"
        cached = _STATUS_CACHE.get(key)
        if cached and time.monotonic() - cached[0] < 30:
            return cached[1]
        installed = ollama_models(self.base_url, self._client)
        if installed is None:
            status = (False, f"Ollama not reachable at {self.base_url} (install from ollama.com, then `ollama serve`)")
        elif not model_present(self.model, installed):
            status = (False, f"Ollama is running but model '{self.model}' is not pulled (`ollama pull {self.model}`)")
        else:
            status = (True, f"Local model {self.model}")
        _STATUS_CACHE[key] = (time.monotonic(), status)
        return status

    def _structured(self, task: str, system: str, user: str, schema: type[T]) -> T:
        body = {
            "model": self.model,
            "stream": False,
            "format": strict_json_schema(schema),
            "options": {"temperature": 0},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        try:
            r = self.client.post(f"{self.base_url}/api/chat", json=body)
            r.raise_for_status()
            content = r.json()["message"]["content"]
        except httpx.HTTPStatusError as exc:
            raise ProviderError(f"Ollama error {exc.response.status_code}: {exc.response.text[:200]}") from exc
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise ProviderError(f"Ollama request failed: {exc}") from exc
        return self._parse(schema, content)
