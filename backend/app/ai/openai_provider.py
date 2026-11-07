"""OpenAI provider (official ``openai`` SDK, Chat Completions with strict JSON schema)."""

from __future__ import annotations

import os

import openai

from ..config import get_settings
from .base import ProviderError, T, strict_json_schema
from .llm import LLMProvider


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, client: openai.OpenAI | None = None, model: str | None = None):
        settings = get_settings()
        self.model = model or settings.openai_model
        self._api_key = settings.openai_api_key
        self._client = client

    @property
    def client(self) -> openai.OpenAI:
        if self._client is None:
            kwargs = {"max_retries": 2, "timeout": 180.0}
            if self._api_key:
                kwargs["api_key"] = self._api_key
            self._client = openai.OpenAI(**kwargs)
        return self._client

    def available(self) -> tuple[bool, str]:
        if self._client is not None:
            return True, "client injected"
        if self._api_key or os.environ.get("OPENAI_API_KEY"):
            return True, f"API key configured, model {self.model}"
        return False, "Set OPENAI_API_KEY to enable OpenAI"

    def _structured(self, task: str, system: str, user: str, schema: type[T]) -> T:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": task, "schema": strict_json_schema(schema), "strict": True},
                },
            )
        except openai.AuthenticationError as exc:
            raise ProviderError("OpenAI rejected the API key") from exc
        except openai.RateLimitError as exc:
            raise ProviderError("OpenAI rate limit reached") from exc
        except openai.APIStatusError as exc:
            raise ProviderError(f"OpenAI API error {exc.status_code}") from exc
        except openai.APIConnectionError as exc:
            raise ProviderError("Could not reach the OpenAI API") from exc

        choice = response.choices[0]
        if getattr(choice.message, "refusal", None):
            raise ProviderError(f"OpenAI refused: {choice.message.refusal}")
        if choice.finish_reason == "length":
            raise ProviderError(f"OpenAI hit the length limit on {task}")
        if not choice.message.content:
            raise ProviderError("OpenAI returned empty content")
        return self._parse(schema, choice.message.content)
