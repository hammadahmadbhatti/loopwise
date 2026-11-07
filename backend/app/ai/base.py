"""Provider-neutral AI contracts.

Every provider (Claude, OpenAI, Ollama, offline heuristics) returns the same
Pydantic objects, so the rest of the app never knows which model ran.
"""

from __future__ import annotations

import copy
from abc import ABC, abstractmethod
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, field_validator

Category = Literal[
    "bug", "feature_request", "usability", "performance", "pricing", "support", "praise", "question", "other"
]
CATEGORIES: list[str] = list(Category.__args__)  # type: ignore[attr-defined]
Urgency = Literal["low", "medium", "high", "critical"]
URGENCIES: list[str] = list(Urgency.__args__)  # type: ignore[attr-defined]
SentimentLabel = Literal["negative", "neutral", "positive"]
Recommendation = Literal["build_now", "build_later", "investigate", "decline"]


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(v)))


class FeedbackAnalysis(BaseModel):
    language: str
    translation: str
    summary: str
    sentiment: float
    sentiment_label: SentimentLabel
    category: Category
    urgency: Urgency
    churn_risk: bool
    keywords: list[str]

    @field_validator("sentiment")
    @classmethod
    def _sentiment_range(cls, v: float) -> float:
        return _clamp(v, -1.0, 1.0)

    @field_validator("language")
    @classmethod
    def _lang(cls, v: str) -> str:
        return (v or "und").strip().lower()[:12]

    @field_validator("keywords")
    @classmethod
    def _kw(cls, v: list[str]) -> list[str]:
        return [k.strip().lower() for k in v if k and k.strip()][:8]


class ThemeLabel(BaseModel):
    name: str
    description: str

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return v.strip().strip('"')[:120] or "Untitled theme"


class EvidenceQuote(BaseModel):
    feedback_id: int
    quote: str
    why_it_matters: str


class DecisionOption(BaseModel):
    title: str
    pros: list[str]
    cons: list[str]


class DecisionBrief(BaseModel):
    summary: str
    problem: str
    affected_segments: list[str]
    evidence: list[EvidenceQuote]
    risks: list[str]
    options: list[DecisionOption]
    recommendation: Recommendation
    rationale: str
    confidence: float
    suggested_impact: float
    suggested_confidence: float

    @field_validator("confidence", "suggested_confidence")
    @classmethod
    def _unit(cls, v: float) -> float:
        return _clamp(v, 0.0, 1.0)

    @field_validator("suggested_impact")
    @classmethod
    def _impact(cls, v: float) -> float:
        # Snap to the standard RICE impact scale
        scale = [0.25, 0.5, 1.0, 2.0, 3.0]
        return min(scale, key=lambda s: abs(s - float(v)))


class AskAnswer(BaseModel):
    answer: str
    cited_feedback_ids: list[int]
    follow_up_questions: list[str]


class Message(BaseModel):
    """A customer-facing message (release note, ship notification)."""

    subject: str
    body: str


T = TypeVar("T", bound=BaseModel)


class ProviderError(RuntimeError):
    """Raised when a provider can't produce a valid result (network, refusal, bad JSON...)."""


class AIProvider(ABC):
    """Interface every provider implements."""

    name: str = "base"
    model: str = ""

    @property
    def label(self) -> str:
        return f"{self.name}:{self.model}" if self.model else self.name

    @abstractmethod
    def available(self) -> tuple[bool, str]:
        """(is_available, human-readable reason)."""

    @abstractmethod
    def analyze_feedback(self, text: str, *, working_language: str, context: dict[str, Any]) -> FeedbackAnalysis: ...

    @abstractmethod
    def label_theme(self, samples: list[str], *, keywords: list[str]) -> ThemeLabel: ...

    @abstractmethod
    def decision_brief(self, payload: dict[str, Any]) -> DecisionBrief: ...

    @abstractmethod
    def answer_question(self, question: str, items: list[dict[str, Any]], stats: dict[str, Any]) -> AskAnswer: ...

    @abstractmethod
    def release_note(self, payload: dict[str, Any]) -> Message: ...

    @abstractmethod
    def localize(self, message: Message, target_language: str) -> Message: ...


def strict_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Pydantic schema -> the strict subset both Claude and OpenAI structured outputs accept.

    Inlines $refs, drops titles/defaults/numeric bounds, requires every property and
    forbids extra keys. Range checks happen afterwards in the Pydantic validators.
    """
    raw = model.model_json_schema()
    defs = raw.pop("$defs", {})
    dropped = {"title", "default", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
               "minLength", "maxLength", "format", "examples", "description"}

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                name = node["$ref"].split("/")[-1]
                return walk(copy.deepcopy(defs[name]))
            out = {k: walk(v) for k, v in node.items() if k not in dropped}
            if out.get("type") == "object" and "properties" in out:
                out["required"] = list(out["properties"].keys())
                out["additionalProperties"] = False
            return out
        if isinstance(node, list):
            return [walk(x) for x in node]
        return node

    return walk(raw)
