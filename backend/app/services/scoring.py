"""Evidence metrics and the explainable priority score for opportunities.

The score is a weighted blend of normalized components, each 0..1, relative to
the other open opportunities in the workspace:

  demand    log-scaled unique customers (+ half weight for portal votes)
  revenue   monthly revenue of affected customers
  pain      negative sentiment, urgency and share of customers at churn risk
  momentum  growth in mentions, last 30 days vs the 30 before
  reach     number of countries affected
  rice      classic RICE score when the team has filled it in

Weights are configurable per workspace; every component is returned so the UI
can show exactly why an item ranks where it does.
"""

from __future__ import annotations

import math
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..deps import workspace_settings
from ..models import Customer, Feedback, Opportunity, OpportunityFeedback, Vote, Workspace

URGENCY_WEIGHT = {"low": 0.1, "medium": 0.4, "high": 0.75, "critical": 1.0}
OPEN_STATUSES = ("under_review", "planned", "in_progress")


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def evidence_items(db: Session, opp: Opportunity) -> list[Feedback]:
    linked = select(OpportunityFeedback.feedback_id).where(OpportunityFeedback.opportunity_id == opp.id)
    cond = Feedback.id.in_(linked)
    if opp.theme_id:
        cond = or_(cond, Feedback.theme_id == opp.theme_id)
    return list(
        db.scalars(
            select(Feedback)
            .where(Feedback.workspace_id == opp.workspace_id, cond, Feedback.status != "archived")
            .order_by(Feedback.created_at.desc())
        ).unique()
    )


def compute_metrics(db: Session, opp: Opportunity, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    items = evidence_items(db, opp)
    unique = [f for f in items if f.duplicate_of_id is None]
    customers: dict[int, Customer] = {f.customer.id: f.customer for f in unique if f.customer}
    anonymous = sum(1 for f in unique if f.customer is None)
    voters = list(db.scalars(select(Vote.customer_id).where(Vote.opportunity_id == opp.id)))
    voter_only = [cid for cid in voters if cid not in customers]
    if voter_only:
        for c in db.scalars(select(Customer).where(Customer.id.in_(voter_only))):
            customers[c.id] = c

    analyzed = [f for f in unique if f.analysis_status == "done" and f.sentiment is not None]
    sentiments = [f.sentiment for f in analyzed]
    churn_customers = {f.customer_id or -f.id for f in analyzed if f.churn_risk}
    countries = sorted({(f.country or (f.customer.country if f.customer else "")).strip() for f in unique} - {""})
    languages = [lang for lang, _ in Counter(f.language for f in analyzed if f.language and f.language != "und").most_common()]
    plans = Counter((c.plan or "Unknown") for c in customers.values())
    recent = sum(1 for f in unique if _aware(f.created_at) >= now - timedelta(days=30))
    prior = sum(1 for f in unique if now - timedelta(days=60) <= _aware(f.created_at) < now - timedelta(days=30))
    growth = None if recent == prior == 0 else ((recent - prior) / prior * 100 if prior else 100.0)
    rice = None
    if all(v is not None for v in (opp.reach, opp.impact, opp.confidence, opp.effort)) and opp.effort:
        rice = round(opp.reach * opp.impact * opp.confidence / opp.effort, 2)
    people = len(customers) + anonymous

    return {
        "mentions": len(unique),
        "duplicates": len(items) - len(unique),
        "customers": people,
        "known_customers": len(customers),
        "votes": len(voters),
        "mrr": round(sum(c.mrr or 0 for c in customers.values()), 2),
        "avg_sentiment": round(sum(sentiments) / len(sentiments), 3) if sentiments else None,
        "negative_share": round(sum(1 for s in sentiments if s < -0.2) / len(sentiments), 3) if sentiments else 0.0,
        "urgency_score": round(sum(URGENCY_WEIGHT.get(f.urgency, 0.1) for f in analyzed) / len(analyzed), 3) if analyzed else 0.0,
        "urgency_mix": dict(Counter(f.urgency for f in analyzed if f.urgency)),
        "churn_risk": len(churn_customers),
        "countries": countries,
        "languages": languages,
        "plans": dict(plans),
        "categories": dict(Counter(f.category for f in analyzed if f.category).most_common(5)),
        "recent_30": recent,
        "prior_30": prior,
        "growth_pct": round(growth, 1) if growth is not None else None,
        "rice_score": rice,
        "first_seen": min((_aware(f.created_at) for f in unique), default=None),
        "last_seen": max((_aware(f.created_at) for f in unique), default=None),
    }


def score_opportunities(db: Session, ws: Workspace, opps: list[Opportunity]) -> dict[int, dict[str, Any]]:
    weights = workspace_settings(ws)["priority_weights"]
    metrics = {o.id: compute_metrics(db, o) for o in opps}
    pool = [metrics[o.id] for o in opps if o.status in OPEN_STATUSES] or list(metrics.values())

    def demand_raw(m: dict) -> float:
        return math.log1p(m["customers"] + 0.5 * m["votes"])

    max_demand = max((demand_raw(m) for m in pool), default=0) or 1
    max_mrr = max((m["mrr"] for m in pool), default=0) or 0
    max_countries = max((len(m["countries"]) for m in pool), default=0) or 1
    max_rice = max((m["rice_score"] or 0 for m in pool), default=0) or 0

    out: dict[int, dict[str, Any]] = {}
    for o in opps:
        m = metrics[o.id]
        neg = max(0.0, -(m["avg_sentiment"] or 0.0))
        churn_share = m["churn_risk"] / m["customers"] if m["customers"] else 0.0
        comps: dict[str, float | None] = {
            "demand": min(1.0, demand_raw(m) / max_demand),
            "revenue": min(1.0, m["mrr"] / max_mrr) if max_mrr else 0.0,
            "pain": min(1.0, 0.5 * neg + 0.3 * m["urgency_score"] + 0.2 * churn_share),
            "momentum": 0.0 if m["growth_pct"] is None else 0.5 + 0.5 * math.tanh(m["growth_pct"] / 100),
            "reach": min(1.0, len(m["countries"]) / max_countries),
            "rice": (m["rice_score"] / max_rice) if (m["rice_score"] and max_rice) else None,
        }
        active = {k: v for k, v in comps.items() if v is not None and weights.get(k, 0) > 0}
        total_w = sum(weights[k] for k in active) or 1
        score = 100 * sum(weights[k] * v for k, v in active.items()) / total_w
        breakdown = [
            {"component": k, "value": round(v, 3), "weight": weights.get(k, 0),
             "contribution": round(100 * weights.get(k, 0) * v / total_w, 1) if k in active else 0.0}
            for k, v in comps.items() if v is not None
        ]
        if m["mentions"] == 0 and m["votes"] == 0:
            score = 0.0
        out[o.id] = {"metrics": m, "priority_score": round(score, 1), "breakdown": breakdown}
    return out


def brief_payload(db: Session, ws: Workspace, opp: Opportunity, scored: dict[str, Any]) -> dict[str, Any]:
    """Everything the AI needs for a decision brief: numbers plus a balanced set of real quotes."""
    items = [f for f in evidence_items(db, opp) if f.duplicate_of_id is None and f.analysis_status == "done"]
    picks: list[Feedback] = []
    for ordering in (
        sorted(items, key=lambda f: f.sentiment if f.sentiment is not None else 0),  # most negative
        sorted(items, key=lambda f: -(f.customer.mrr if f.customer else 0)),  # biggest accounts
        sorted(items, key=lambda f: _aware(f.created_at), reverse=True),  # most recent
    ):
        for f in ordering[:5]:
            if f not in picks:
                picks.append(f)
    quotes = [
        {
            "feedback_id": f.id,
            "text": f.working_text[:500],
            "original_language": f.language,
            "country": f.country or (f.customer.country if f.customer else ""),
            "plan": f.customer.plan if f.customer else "",
            "mrr": f.customer.mrr if f.customer else 0,
            "sentiment": f.sentiment,
            "category": f.category,
            "urgency": f.urgency,
            "churn_risk": f.churn_risk,
        }
        for f in picks[:15]
    ]
    m = dict(scored["metrics"])
    m.pop("first_seen", None)
    m.pop("last_seen", None)
    m["priority_score"] = scored["priority_score"]
    return {
        "working_language": workspace_settings(ws).get("working_language", "en"),
        "opportunity": {"title": opp.title, "description": opp.description, "status": opp.status,
                        "theme": opp.theme.name if opp.theme else None},
        "metrics": m,
        "score_breakdown": scored["breakdown"],
        "quotes": quotes,
    }


def vote_count(db: Session, opp_id: int) -> int:
    return db.scalar(select(func.count()).select_from(Vote).where(Vote.opportunity_id == opp_id)) or 0
