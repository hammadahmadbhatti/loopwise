"""Provider selection and automatic fallback.

Order for ``auto``: Claude -> OpenAI -> Ollama (local) -> offline heuristics.
If the chosen provider fails at request time (network, rate limit, refusal,
invalid output), the task is re-run on the offline engine so the product keeps
working, and the result is labelled with what actually produced it.
"""

from __future__ import annotations

import logging
from typing import Any

from ..config import get_settings
from .anthropic_provider import AnthropicProvider
from .base import AIProvider, ProviderError
from .heuristic import HeuristicProvider
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider

log = logging.getLogger("loopwise.ai")

PROVIDER_ORDER = ["anthropic", "openai", "ollama", "heuristic"]
PROVIDER_TITLES = {
    "anthropic": "Claude (Anthropic)",
    "openai": "OpenAI",
    "ollama": "Ollama (free, local)",
    "heuristic": "Offline engine (built-in)",
}
_FACTORIES = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "ollama": OllamaProvider,
    "heuristic": HeuristicProvider,
}
_INSTANCES: dict[str, AIProvider] = {}


def get_provider(name: str) -> AIProvider:
    if name not in _FACTORIES:
        raise ValueError(f"Unknown AI provider '{name}'")
    if name not in _INSTANCES:
        _INSTANCES[name] = _FACTORIES[name]()
    return _INSTANCES[name]


def override_provider(name: str, instance: AIProvider | None) -> None:
    """Swap in a provider instance (used by tests); None resets to the default factory."""
    if instance is None:
        _INSTANCES.pop(name, None)
    else:
        _INSTANCES[name] = instance


def provider_status() -> list[dict[str, Any]]:
    out = []
    for name in PROVIDER_ORDER:
        p = get_provider(name)
        ok, reason = p.available()
        out.append({"name": name, "title": PROVIDER_TITLES[name], "model": p.model, "available": ok, "detail": reason})
    return out


def resolve_provider(preference: str | None) -> tuple[AIProvider, str]:
    """Pick a provider for a workspace preference. Returns (provider, note)."""
    pref = preference if preference and preference != "default" else get_settings().ai_provider
    if pref == "auto":
        for name in PROVIDER_ORDER:
            p = get_provider(name)
            if p.available()[0]:
                return p, f"auto-selected {name}"
        return get_provider("heuristic"), "auto-selected heuristic"
    p = get_provider(pref)
    ok, reason = p.available()
    if ok:
        return p, f"configured {pref}"
    return get_provider("heuristic"), f"{pref} unavailable ({reason}); using offline engine"


class AIService:
    """Runs AI tasks on the workspace's provider with automatic offline fallback."""

    def __init__(self, preference: str | None = None):
        self.primary, self.note = resolve_provider(preference)
        self.fallback = get_provider("heuristic")

    @property
    def is_offline(self) -> bool:
        return self.primary.name == "heuristic"

    def run(self, task: str, *args: Any, **kwargs: Any) -> tuple[Any, str, str]:
        """Return (result, produced_by_label, error_message_or_empty)."""
        try:
            return getattr(self.primary, task)(*args, **kwargs), self.primary.label, ""
        except (ProviderError, Exception) as exc:  # noqa: BLE001 - any provider failure falls back
            if self.primary is self.fallback:
                raise
            log.warning("AI task %s failed on %s: %s; falling back to offline engine", task, self.primary.label, exc)
            result = getattr(self.fallback, task)(*args, **kwargs)
            return result, f"{self.fallback.label} (fallback from {self.primary.name})", str(exc)[:500]
