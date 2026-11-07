"""Prompts shared by every LLM provider (Claude, OpenAI, Ollama).

System prompts are static strings so providers can cache them; all per-request
data goes in the user message.
"""

from __future__ import annotations

import json
from typing import Any

LANGUAGE_NAMES = {
    "en": "English", "de": "German", "es": "Spanish", "fr": "French", "pt": "Portuguese", "it": "Italian",
    "nl": "Dutch", "pl": "Polish", "sv": "Swedish", "da": "Danish", "no": "Norwegian", "fi": "Finnish",
    "tr": "Turkish", "ru": "Russian", "uk": "Ukrainian", "ar": "Arabic", "hi": "Hindi", "ur": "Urdu",
    "ja": "Japanese", "ko": "Korean", "zh-cn": "Chinese", "zh": "Chinese", "id": "Indonesian", "ms": "Malay",
    "vi": "Vietnamese", "th": "Thai", "cs": "Czech", "ro": "Romanian", "el": "Greek", "he": "Hebrew",
}


def language_name(code: str) -> str:
    return LANGUAGE_NAMES.get((code or "").lower(), code or "the original language")


ANALYZE_SYSTEM = """You analyze customer feedback for a product team that serves customers worldwide.

For each piece of feedback, return:
- language: ISO 639-1 code of the feedback's language (e.g. "en", "de", "es", "ja").
- translation: a faithful translation into the team's working language. If the feedback is already in the working language, return an empty string.
- summary: one short sentence in the working language describing what the customer is saying or asking for. Neutral wording, no greeting.
- sentiment: a number from -1.0 (very negative) to 1.0 (very positive); 0 is neutral.
- sentiment_label: "negative" (sentiment < -0.2), "positive" (> 0.2), otherwise "neutral".
- category: the single best fit:
  bug (something is broken or erroring), feature_request (asks for new capability),
  usability (confusing or hard to use), performance (slow, timeouts, resource use),
  pricing (price, billing, plans, invoices), support (about help/service quality),
  praise (positive with no request), question (asks how to do something), other.
- urgency: "critical" (data loss, security, outage, payments failing, can't log in, legal),
  "high" (core workflow blocked or customer threatening to leave), "medium" (real pain with a workaround),
  "low" (nice to have, praise, general comments).
- churn_risk: true only if the customer signals they may cancel, downgrade, switch to a competitor or ask for a refund.
- keywords: 2 to 5 short lowercase topic keywords in the working language (nouns or short noun phrases, no sentiment words).

Judge the text itself; a star rating, if given, is supporting context only."""


def analyze_user(text: str, working_language: str, context: dict[str, Any]) -> str:
    ctx = {k: v for k, v in context.items() if v not in (None, "", [], {})}
    return (
        f"Working language: {language_name(working_language)} ({working_language})\n"
        f"Context: {json.dumps(ctx, ensure_ascii=False, sort_keys=True)}\n\n"
        f"<feedback>\n{text}\n</feedback>"
    )


THEME_SYSTEM = """You name clusters of customer feedback for a product team.
Given sample feedback that an embedding model grouped together, return:
- name: a 2 to 6 word label for the shared underlying topic, written like a product backlog item
  (e.g. "CSV export for reports", "Login fails after password reset"). No quotes, no trailing period.
- description: one sentence explaining what these customers have in common.
Base the label on what most samples share, not on outliers."""


def theme_user(samples: list[str], keywords: list[str]) -> str:
    lines = "\n".join(f"- {s[:400]}" for s in samples)
    return f"Frequent keywords: {', '.join(keywords)}\n\nSample feedback:\n{lines}"


BRIEF_SYSTEM = """You are a senior product strategist writing a decision brief for a product team.
You receive one product opportunity with quantitative evidence (customer counts, revenue of affected
customers, sentiment, urgency, churn signals, trend, votes, countries) and representative customer quotes
(each with a feedback_id).

Write a concise, evidence-based brief:
- summary: 2 to 3 sentences a busy executive can act on.
- problem: the underlying customer problem, not the requested solution.
- affected_segments: who is affected (plans, countries, languages, customer types), grounded in the data.
- evidence: 3 to 6 of the most telling quotes. Use only feedback_ids from the input, quote them faithfully
  (translated text is fine) and say why each matters.
- risks: risks of acting and of not acting.
- options: 2 to 3 realistic options (for example full solution, minimal version, defer) with pros and cons.
- recommendation: build_now, build_later, investigate (evidence too thin or unclear), or decline.
- rationale: why this recommendation, referencing the numbers.
- confidence: 0 to 1, how sure you are given the amount and consistency of evidence.
- suggested_impact: RICE impact on the scale 0.25 (minimal), 0.5 (low), 1 (medium), 2 (high), 3 (massive).
- suggested_confidence: RICE confidence from 0 to 1.

Never invent numbers or quotes that are not in the input. If the evidence is thin, say so."""


def brief_user(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=1, default=str)


ASK_SYSTEM = """You answer a product team's questions using only the customer feedback provided.
Each feedback item has an id, text (translated into the working language when needed) and metadata.
Rules:
- Answer in 1 to 3 short paragraphs or a short bulleted list. Lead with the direct answer.
- Cite supporting feedback inline as [#id]; put every cited id in cited_feedback_ids.
- Use the provided statistics for counts and percentages; don't invent numbers.
- If the feedback doesn't answer the question, say so plainly.
- follow_up_questions: 2 to 3 useful next questions the team could ask."""


def ask_user(question: str, items: list[dict[str, Any]], stats: dict[str, Any]) -> str:
    return (
        f"Question: {question}\n\n"
        f"Statistics for the retrieved feedback: {json.dumps(stats, ensure_ascii=False, sort_keys=True)}\n\n"
        f"Feedback items:\n{json.dumps(items, ensure_ascii=False, indent=1, default=str)}"
    )


RELEASE_NOTE_SYSTEM = """You write short, warm product release notes that close the loop with customers
who asked for something. Return:
- subject: an email subject line under 70 characters announcing the shipped improvement.
- body: 60 to 140 words of plain text. Start with "Hi {{name}}," on its own line (keep the {{name}}
  placeholder exactly as written). Thank them for their feedback, explain what changed and how it helps,
  and end with an invitation to reply with more feedback. No markdown, no made-up details or dates."""


def release_note_user(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=1, default=str)


LOCALIZE_SYSTEM = """You translate customer emails. Keep the meaning, tone and line breaks.
Keep placeholders such as {{name}} exactly as they are. Keep product and feature names that are
proper nouns untranslated. Return the translated subject and body."""


def localize_user(subject: str, body: str, target_language: str) -> str:
    return (
        f"Target language: {language_name(target_language)} ({target_language})\n\n"
        f"Subject: {subject}\n\nBody:\n{body}"
    )
