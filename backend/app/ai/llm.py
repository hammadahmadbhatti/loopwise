"""Shared implementation for LLM-backed providers.

Claude, OpenAI and Ollama only differ in how they make one schema-constrained
call (``_structured``). Every task method is written once here.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Any

from pydantic import ValidationError

from . import prompts
from .base import (
    AIProvider,
    AskAnswer,
    DecisionBrief,
    FeedbackAnalysis,
    Message,
    ProviderError,
    T,
    ThemeLabel,
)

# How much reasoning each task deserves: (effort, max_tokens).
# Classification-style tasks are cheap and frequent; the decision brief is the one place to spend.
TASK_BUDGET: dict[str, tuple[str, int]] = {
    "analyze_feedback": ("low", 4000),
    "label_theme": ("low", 2000),
    "decision_brief": ("high", 16000),
    "answer_question": ("medium", 8000),
    "release_note": ("low", 3000),
    "localize": ("low", 3000),
}


class LLMProvider(AIProvider):
    @abstractmethod
    def _structured(self, task: str, system: str, user: str, schema: type[T]) -> T:
        """One request whose output is constrained to ``schema``'s JSON schema."""

    @staticmethod
    def _parse(schema: type[T], text: str) -> T:
        try:
            return schema.model_validate_json(text)
        except ValidationError as exc:
            raise ProviderError(f"Model returned invalid JSON for {schema.__name__}: {exc.errors()[:2]}") from exc

    def analyze_feedback(self, text: str, *, working_language: str, context: dict[str, Any]) -> FeedbackAnalysis:
        result = self._structured(
            "analyze_feedback",
            prompts.ANALYZE_SYSTEM,
            prompts.analyze_user(text, working_language, context),
            FeedbackAnalysis,
        )
        if result.language.split("-")[0] == working_language.split("-")[0]:
            result.translation = ""
        return result

    def label_theme(self, samples: list[str], *, keywords: list[str]) -> ThemeLabel:
        return self._structured("label_theme", prompts.THEME_SYSTEM, prompts.theme_user(samples, keywords), ThemeLabel)

    def decision_brief(self, payload: dict[str, Any]) -> DecisionBrief:
        brief = self._structured("decision_brief", prompts.BRIEF_SYSTEM, prompts.brief_user(payload), DecisionBrief)
        allowed = {q["feedback_id"] for q in payload.get("quotes", [])}
        brief.evidence = [e for e in brief.evidence if e.feedback_id in allowed]  # drop invented citations
        return brief

    def answer_question(self, question: str, items: list[dict[str, Any]], stats: dict[str, Any]) -> AskAnswer:
        answer = self._structured(
            "answer_question", prompts.ASK_SYSTEM, prompts.ask_user(question, items, stats), AskAnswer
        )
        allowed = {i["id"] for i in items}
        answer.cited_feedback_ids = [i for i in answer.cited_feedback_ids if i in allowed]
        return answer

    def release_note(self, payload: dict[str, Any]) -> Message:
        return self._structured(
            "release_note", prompts.RELEASE_NOTE_SYSTEM, prompts.release_note_user(payload), Message
        )

    def localize(self, message: Message, target_language: str) -> Message:
        return self._structured(
            "localize",
            prompts.LOCALIZE_SYSTEM,
            prompts.localize_user(message.subject, message.body, target_language),
            Message,
        )
