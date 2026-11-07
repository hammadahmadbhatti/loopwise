"""Contract tests for the AI providers using fake SDK clients (no network, no cost)."""

import json
from types import SimpleNamespace as NS

import httpx
import pytest

from app.ai import registry
from app.ai.anthropic_provider import FALLBACK_BETA, AnthropicProvider
from app.ai.base import DecisionBrief, FeedbackAnalysis, ProviderError, strict_json_schema
from app.ai.ollama_provider import OllamaProvider
from app.ai.openai_provider import OpenAIProvider

ANALYSIS = {
    "language": "de", "translation": "The dashboard is very slow.", "summary": "Dashboard is slow.",
    "sentiment": -0.7, "sentiment_label": "negative", "category": "performance", "urgency": "medium",
    "churn_risk": False, "keywords": ["dashboard", "speed"],
}


class FakeAnthropic:
    def __init__(self, payload=None, stop_reason="end_turn"):
        self.calls = []
        self.payload, self.stop_reason = payload or ANALYSIS, stop_reason
        self.beta = NS(messages=NS(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return NS(stop_reason=self.stop_reason, stop_details=NS(category="cyber"),
                  content=[NS(type="thinking", thinking=""), NS(type="text", text=json.dumps(self.payload))])


def test_strict_schema_is_closed_and_fully_required():
    s = strict_json_schema(DecisionBrief)
    assert s["additionalProperties"] is False and set(s["required"]) == set(s["properties"])
    item = s["properties"]["evidence"]["items"]
    assert item["additionalProperties"] is False and "$ref" not in json.dumps(s)
    assert "title" not in json.dumps(s)


def test_claude_request_shape_and_parsing():
    fake = FakeAnthropic()
    p = AnthropicProvider(client=fake)
    result = p.analyze_feedback("Das Dashboard ist sehr langsam.", working_language="en", context={"rating": 2})
    assert isinstance(result, FeedbackAnalysis) and result.category == "performance"
    call = fake.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["betas"] == [FALLBACK_BETA] and call["fallbacks"] == "default"
    assert call["output_config"]["effort"] == "low"
    assert call["output_config"]["format"]["type"] == "json_schema"
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "thinking" not in call and "temperature" not in call  # thinking is adaptive by default on Opus 5.5
    assert "<feedback>" in call["messages"][0]["content"]


def test_claude_uses_more_effort_for_briefs():
    brief = {"summary": "s", "problem": "p", "affected_segments": [], "evidence": [{"feedback_id": 1, "quote": "q", "why_it_matters": "w"}, {"feedback_id": 999, "quote": "made up", "why_it_matters": "x"}],
             "risks": [], "options": [], "recommendation": "build_now", "rationale": "r", "confidence": 1.4,
             "suggested_impact": 1.7, "suggested_confidence": 0.8}
    fake = FakeAnthropic(payload=brief)
    out = AnthropicProvider(client=fake).decision_brief({"quotes": [{"feedback_id": 1}], "metrics": {}, "opportunity": {}})
    assert fake.calls[0]["output_config"]["effort"] == "high"
    assert [e.feedback_id for e in out.evidence] == [1]  # invented citation dropped
    assert out.confidence == 1.0 and out.suggested_impact == 2.0  # clamped / snapped to RICE scale


def test_claude_refusal_raises():
    with pytest.raises(ProviderError, match="declined"):
        AnthropicProvider(client=FakeAnthropic(stop_reason="refusal")).label_theme(["x"], keywords=[])


def test_openai_request_shape():
    calls = []

    def create(**kw):
        calls.append(kw)
        return NS(choices=[NS(finish_reason="stop", message=NS(refusal=None, content=json.dumps(ANALYSIS)))])

    p = OpenAIProvider(client=NS(chat=NS(completions=NS(create=create))), model="gpt-test")
    assert p.analyze_feedback("x", working_language="en", context={}).language == "de"
    rf = calls[0]["response_format"]
    assert rf["type"] == "json_schema" and rf["json_schema"]["strict"] is True
    assert calls[0]["model"] == "gpt-test"


def test_ollama_availability_and_chat():
    seen = {}

    def handler(request: httpx.Request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen2.5:7b"}]})
        body = json.loads(request.content)
        seen.update(body)
        return httpx.Response(200, json={"message": {"content": json.dumps(ANALYSIS)}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    p = OllamaProvider(client=client, base_url="http://ollama.test", model="qwen2.5:7b")
    assert p.available()[0] is True
    assert p.analyze_feedback("x", working_language="en", context={}).category == "performance"
    assert seen["format"]["type"] == "object" and seen["stream"] is False

    missing = OllamaProvider(client=client, base_url="http://ollama.test", model="llama3.2")
    ok, reason = missing.available()
    assert ok is False and "ollama pull llama3.2" in reason


def test_ollama_invalid_json_raises():
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"message": {"content": "not json"}})))
    with pytest.raises(ProviderError):
        OllamaProvider(client=client, base_url="http://o.test").label_theme(["a"], keywords=[])


def test_fallback_to_offline_engine_when_provider_fails():
    class Broken(AnthropicProvider):
        def available(self):
            return True, "pretend"

        def _structured(self, *a, **k):
            raise ProviderError("network down")

    registry.override_provider("anthropic", Broken(client=FakeAnthropic()))
    try:
        svc = registry.AIService("anthropic")
        result, by, err = svc.run("analyze_feedback", "The export is broken", working_language="en", context={})
        assert result.category == "bug"
        assert by.startswith("heuristic") and "fallback from anthropic" in by and err == "network down"
    finally:
        registry.override_provider("anthropic", None)


def test_unavailable_preference_resolves_to_offline(monkeypatch):
    monkeypatch.setattr(OpenAIProvider, "available", lambda self: (False, "no key"))
    registry._INSTANCES.clear()
    provider, note = registry.resolve_provider("openai")
    assert provider.name == "heuristic" and "openai unavailable" in note


def test_auto_prefers_claude_when_available(monkeypatch):
    monkeypatch.setattr(AnthropicProvider, "available", lambda self: (True, "key"))
    registry._INSTANCES.clear()
    assert registry.resolve_provider("auto")[0].name == "anthropic"
    registry._INSTANCES.clear()
