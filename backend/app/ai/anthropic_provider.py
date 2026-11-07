"""Claude provider (Anthropic Python SDK).

Uses structured outputs (``output_config.format``) so every reply is schema-valid JSON,
per-task ``effort`` to keep frequent classification calls cheap, and the server-side
``fallbacks: "default"`` option so a safety-classifier refusal is retried on
Anthropic's recommended fallback model instead of failing the request.
"""

from __future__ import annotations

import os

import anthropic

from ..config import get_settings
from .base import ProviderError, T, strict_json_schema
from .llm import TASK_BUDGET, LLMProvider

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, client: anthropic.Anthropic | None = None, model: str | None = None):
        settings = get_settings()
        self.model = model or settings.claude_model
        self._api_key = settings.anthropic_api_key
        self._client = client

    @property
    def client(self) -> anthropic.Anthropic:
        if self._client is None:
            kwargs = {"max_retries": 2, "timeout": 180.0}
            if self._api_key:
                kwargs["api_key"] = self._api_key
            self._client = anthropic.Anthropic(**kwargs)
        return self._client

    def available(self) -> tuple[bool, str]:
        if self._client is not None:
            return True, "client injected"
        if self._api_key or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
            return True, f"API key configured, model {self.model}"
        return False, "Set ANTHROPIC_API_KEY to enable Claude"

    def _structured(self, task: str, system: str, user: str, schema: type[T]) -> T:
        effort, max_tokens = TASK_BUDGET[task]
        try:
            response = self.client.beta.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                betas=[FALLBACK_BETA],
                fallbacks="default",
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                output_config={
                    "effort": effort,
                    "format": {"type": "json_schema", "schema": strict_json_schema(schema)},
                },
                messages=[{"role": "user", "content": user}],
            )
        except anthropic.AuthenticationError as exc:
            raise ProviderError("Claude rejected the API key") from exc
        except anthropic.RateLimitError as exc:
            raise ProviderError("Claude rate limit reached") from exc
        except anthropic.APIStatusError as exc:
            raise ProviderError(f"Claude API error {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderError("Could not reach the Claude API") from exc

        if response.stop_reason == "refusal":
            category = getattr(getattr(response, "stop_details", None), "category", None)
            raise ProviderError(f"Claude declined the request (category: {category})")
        if response.stop_reason == "max_tokens":
            raise ProviderError(f"Claude hit max_tokens on {task}")
        text = next((b.text for b in response.content if b.type == "text"), None)
        if not text:
            raise ProviderError("Claude returned no text block")
        return self._parse(schema, text)
