"""Dashboard aggregates, emerging-issue detection and Ask-your-feedback (retrieval + AI answer)."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.embeddings import cosine, get_embedder
from ..ai.registry import AIService
from ..ai.textutil import content_tokens, stem
from ..deps import workspace_settings
from ..models import Feedback, Theme, Workspace
from .scoring import _aware
from .themes import ensure_embeddings


def _feedback_since(db: Session, ws_id: int, since: datetime) -> list[Feedback]:
    return list(
        db.scalars(
            select(Feedback)
            .where(Feedback.workspace_id == ws_id, Feedback.created_at >= since, Feedback.status != "archived")
            .order_by(Feedback.created_at)
        )
    )


def theme_trends(db: Session, ws_id: int, now: datetime | None = None) -> dict[int, dict[str, Any]]:
    """Per-theme counts for the last 8 weeks plus emerging-issue flag."""
    now = now or datetime.now(timezone.utc)
    items = _feedback_since(db, ws_id, now - timedelta(weeks=8))
    weekly: dict[int, list[int]] = defaultdict(lambda: [0] * 8)
    for f in items:
        if f.theme_id and f.duplicate_of_id is None:
            age_weeks = min(7, int((now - _aware(f.created_at)).days // 7))
            weekly[f.theme_id][7 - age_weeks] += 1
    out = {}
    for tid, series in weekly.items():
        this_week = series[-1]
        baseline = sum(series[3:7]) / 4
        emerging = this_week >= 3 and this_week >= 2 * max(baseline, 0.5)
        out[tid] = {"weekly": series, "this_week": this_week, "baseline": round(baseline, 2), "emerging": emerging}
    return out


def overview(db: Session, ws: Workspace, days: int = 30) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days)
    prev_since = since - timedelta(days=days)
    items = _feedback_since(db, ws.id, prev_since)
    current = [f for f in items if _aware(f.created_at) >= since]
    previous = [f for f in items if _aware(f.created_at) < since]
    analyzed = [f for f in current if f.analysis_status == "done" and f.sentiment is not None]

    def avg(vals: list[float]) -> float | None:
        return round(sum(vals) / len(vals), 3) if vals else None

    prev_analyzed = [f.sentiment for f in previous if f.sentiment is not None]
    ratings = [f.rating for f in current if f.rating]

    # daily series split by sentiment
    series: dict[str, dict[str, int]] = {}
    for i in range(days):
        day = (since + timedelta(days=i + 1)).date().isoformat()
        series[day] = {"positive": 0, "neutral": 0, "negative": 0, "pending": 0}
    for f in current:
        day = _aware(f.created_at).date().isoformat()
        if day in series:
            series[day][f.sentiment_label or "pending"] += 1

    countries: dict[str, list[float]] = defaultdict(list)
    for f in current:
        c = f.country or (f.customer.country if f.customer else "") or "Unknown"
        countries[c].append(f.sentiment if f.sentiment is not None else np.nan)

    themes = {t.id: t for t in db.scalars(select(Theme).where(Theme.workspace_id == ws.id, Theme.archived.is_(False)))}
    trends = theme_trends(db, ws.id, now)
    theme_counts = Counter(f.theme_id for f in current if f.theme_id and f.duplicate_of_id is None)
    theme_sent: dict[int, list[float]] = defaultdict(list)
    for f in analyzed:
        if f.theme_id:
            theme_sent[f.theme_id].append(f.sentiment)

    top_themes = [
        {
            "id": tid, "name": themes[tid].name, "count": n, "avg_sentiment": avg(theme_sent[tid]),
            "weekly": trends.get(tid, {}).get("weekly", [0] * 8), "emerging": trends.get(tid, {}).get("emerging", False),
        }
        for tid, n in theme_counts.most_common(8) if tid in themes
    ]
    emerging = [
        {"id": tid, "name": themes[tid].name, **t} for tid, t in trends.items() if t["emerging"] and tid in themes
    ]
    at_risk = sorted(
        (f for f in analyzed if f.churn_risk or f.urgency == "critical"),
        key=lambda f: (-(f.customer.mrr if f.customer else 0), _aware(f.created_at)),
    )[:8]
    pending = sum(1 for f in items if f.analysis_status in ("pending", "processing"))

    return {
        "days": days,
        "kpis": {
            "feedback": len(current),
            "feedback_prev": len(previous),
            "avg_sentiment": avg([f.sentiment for f in analyzed]),
            "avg_sentiment_prev": avg(prev_analyzed),
            "negative_pct": round(100 * sum(1 for f in analyzed if f.sentiment_label == "negative") / len(analyzed), 1) if analyzed else 0,
            "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
            "languages": len({f.language for f in analyzed if f.language and f.language != "und"}),
            "countries": len([c for c in countries if c != "Unknown"]),
            "churn_signals": sum(1 for f in analyzed if f.churn_risk),
            "customers": len({f.customer_id for f in current if f.customer_id}),
            "pending_analysis": pending,
        },
        "series": [{"date": d, **v} for d, v in series.items()],
        "categories": Counter(f.category for f in analyzed).most_common(),
        "sources": Counter(f.source for f in current).most_common(),
        "languages": Counter(f.language for f in analyzed if f.language).most_common(12),
        "countries": sorted(
            ({"country": c, "count": len(v), "avg_sentiment": avg([x for x in v if not np.isnan(x)])}
             for c, v in countries.items()),
            key=lambda r: -r["count"],
        )[:15],
        "top_themes": top_themes,
        "emerging": emerging,
        "at_risk": [
            {"id": f.id, "summary": f.summary or f.text[:160], "customer": f.customer.name if f.customer else "",
             "company": f.customer.company if f.customer else "", "mrr": f.customer.mrr if f.customer else 0,
             "urgency": f.urgency, "churn_risk": f.churn_risk, "language": f.language,
             "created_at": _aware(f.created_at).isoformat()}
            for f in at_risk
        ],
    }


def _keyword_scores(question: str, items: list[Feedback]) -> np.ndarray:
    q = {stem(t) for t in content_tokens(question)}
    if not q:
        return np.zeros(len(items))
    out = []
    for f in items:
        toks = {stem(t) for t in content_tokens(f.working_text)} | {stem(k) for k in (f.keywords or [])}
        out.append(len(q & toks) / len(q))
    return np.asarray(out)


_INTENTS = {
    "churn": ("cancel", "churn", "leave", "leaving", "switch", "competitor", "refund", "quit", "lose", "losing", "kundig", "cancelar", "annuler"),
    "negative": ("unhappy", "complain", "problem", "issue", "negative", "frustrat", "angry", "bad", "worst", "pain", "hate", "annoy", "wrong"),
    "positive": ("love", "like", "happy", "praise", "positive", "great", "best", "enjoy", "delight", "good"),
}
_LANG_WORDS = {"english": "en", "german": "de", "spanish": "es", "french": "fr", "portuguese": "pt", "brazilian": "pt",
               "italian": "it", "dutch": "nl", "japanese": "ja", "chinese": "zh-cn", "korean": "ko", "arabic": "ar"}


def question_filters(question: str, items: list[Feedback]) -> dict[str, Any]:
    """Structured hints in a natural-language question: intent, plan, language, country, time window."""
    q = question.lower()
    tokens = set(re.findall(r"[a-z]+", q))
    intents = {name for name, words in _INTENTS.items() if any(t.startswith(w) for t in tokens for w in words)}
    plans = {(f.customer.plan or "").lower() for f in items if f.customer and f.customer.plan}
    countries = {f.country.lower() for f in items if f.country}
    return {
        "intents": intents,
        "plan": next((p for p in plans if p and re.search(rf"\b{re.escape(p)}\b", q)), None),
        "language": next((code for word, code in _LANG_WORDS.items() if word in q), None),
        "country": next((c for c in sorted(countries, key=len, reverse=True) if re.search(rf"\b{re.escape(c)}\b", q)), None),
        "days": 7 if "this week" in q or "last week" in q else 30 if ("this month" in q or "last month" in q or "recent" in q) else None,
    }


def ask(db: Session, ws: Workspace, question: str, top_k: int = 25) -> dict[str, Any]:
    """Answer a natural-language question from the workspace's feedback, with citations."""
    embedder = get_embedder()
    items = list(
        db.scalars(
            select(Feedback)
            .where(Feedback.workspace_id == ws.id, Feedback.analysis_status == "done",
                   Feedback.duplicate_of_id.is_(None), Feedback.status != "archived")
            .order_by(Feedback.created_at.desc())
            .limit(3000)
        )
    )
    ai = AIService(workspace_settings(ws).get("ai_provider"))
    if not items:
        result, by, _ = ai.run("answer_question", question, [], {})
        return {"answer": result.answer, "citations": [], "follow_up_questions": result.follow_up_questions,
                "answered_by": by, "retrieved": 0}

    ensure_embeddings(db, items, embedder)
    db.commit()
    hints = question_filters(question, items)
    # hard filters from the question (only applied when they actually match something)
    now = datetime.now(timezone.utc)
    for keep in (
        (lambda f: f.customer is not None and (f.customer.plan or "").lower() == hints["plan"]) if hints["plan"] else None,
        (lambda f: f.language == hints["language"]) if hints["language"] else None,
        (lambda f: f.country.lower() == hints["country"]) if hints["country"] else None,
        (lambda f: _aware(f.created_at) >= now - timedelta(days=hints["days"])) if hints["days"] else None,
    ):
        if keep is not None and any(keep(f) for f in items):
            items = [f for f in items if keep(f)]

    q_vec = embedder.embed([question])[0]
    X = embedder.matrix([f.embedding for f in items] + [q_vec])
    sims = cosine(X[-1], X[:-1]).ravel()
    boost = np.zeros(len(items))
    for i, f in enumerate(items):
        s = f.sentiment or 0.0
        if "churn" in hints["intents"] and f.churn_risk:
            boost[i] += 0.5
        if "negative" in hints["intents"]:
            boost[i] += 0.3 * max(0.0, -s)
        if "positive" in hints["intents"]:
            boost[i] += 0.3 * max(0.0, s)
    blended = 0.6 * sims + 0.2 * _keyword_scores(question, items) + boost
    threshold = embedder.retrieval_min + (0.1 if hints["intents"] else 0.0)
    filtered = bool(hints["plan"] or hints["language"] or hints["country"] or hints["days"])
    order = [int(i) for i in np.argsort(-blended)
             if blended[int(i)] >= threshold or (filtered and not hints["intents"])][:top_k]
    picked = [items[i] for i in order]

    payload = [
        {"id": f.id, "text": f.working_text[:600], "language": f.language, "sentiment": f.sentiment,
         "category": f.category, "urgency": f.urgency, "country": f.country,
         "plan": f.customer.plan if f.customer else "", "date": _aware(f.created_at).date().isoformat(),
         "theme": f.theme.name if f.theme else None}
        for f in picked
    ]
    labels = [f.sentiment_label for f in picked]
    stats = {
        "count": len(picked),
        "customers": len({f.customer_id for f in picked if f.customer_id}),
        "countries": sorted({f.country for f in picked if f.country}),
        "negative_pct": round(100 * labels.count("negative") / len(picked)) if picked else 0,
        "positive_pct": round(100 * labels.count("positive") / len(picked)) if picked else 0,
        "top_categories": Counter(f.category for f in picked).most_common(3),
        "top_themes": Counter(f.theme.name for f in picked if f.theme).most_common(3),
    }
    result, by, _ = ai.run("answer_question", question, payload, stats)
    by_id = {f.id: f for f in picked}
    return {
        "answer": result.answer,
        "citations": [
            {"id": i, "text": by_id[i].text[:300], "translated_text": by_id[i].translated_text[:300],
             "language": by_id[i].language, "sentiment_label": by_id[i].sentiment_label}
            for i in result.cited_feedback_ids if i in by_id
        ],
        "follow_up_questions": result.follow_up_questions,
        "answered_by": by,
        "retrieved": len(picked),
        "stats": stats,
    }
