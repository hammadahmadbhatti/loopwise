"""Decision engine: prioritized opportunities, evidence, AI decision briefs and the decision log."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..ai.registry import AIService
from ..db import get_db
from ..deps import WorkspaceContext, get_workspace_ctx, workspace_settings
from ..models import Decision, Feedback, Notification, Opportunity, OpportunityFeedback, Theme, User
from ..schemas import (
    DecisionIn,
    LinkFeedbackIn,
    OpportunityIn,
    OpportunityPatch,
    decision_out,
    feedback_out,
    iso,
)
from ..services.loop import on_shipped
from ..services.scoring import brief_payload, evidence_items, score_opportunities

router = APIRouter(prefix="/api/workspaces/{wid}", tags=["decisions"])

OUTCOME_STATUS = {"build": "planned", "decline": "declined", "defer": "under_review", "investigate": "under_review"}


def _get(db: Session, ctx: WorkspaceContext, oid: int) -> Opportunity:
    o = db.get(Opportunity, oid)
    if o is None or o.workspace_id != ctx.id:
        raise HTTPException(404, "Opportunity not found")
    return o


def _link(db: Session, ctx: WorkspaceContext, opp: Opportunity, ids: list[int]) -> int:
    valid = set(db.scalars(select(Feedback.id).where(Feedback.workspace_id == ctx.id, Feedback.id.in_(ids))))
    existing = set(db.scalars(select(OpportunityFeedback.feedback_id).where(OpportunityFeedback.opportunity_id == opp.id)))
    for fid in valid - existing:
        db.add(OpportunityFeedback(opportunity_id=opp.id, feedback_id=fid))
    return len(valid - existing)


def create_opportunity(db: Session, ctx: WorkspaceContext, body: OpportunityIn) -> Opportunity:
    if body.theme_id is not None:
        theme = db.get(Theme, body.theme_id)
        if theme is None or theme.workspace_id != ctx.id:
            raise HTTPException(404, "Theme not found")
    opp = Opportunity(workspace_id=ctx.id, title=body.title.strip(), description=body.description.strip(),
                      theme_id=body.theme_id, is_public=body.is_public, created_by=ctx.user.id)
    db.add(opp)
    db.flush()
    if body.feedback_ids:
        _link(db, ctx, opp, body.feedback_ids)
    return opp


def opportunity_out(o: Opportunity, scored: dict) -> dict:
    m = scored["metrics"]
    return {
        "id": o.id, "title": o.title, "description": o.description, "status": o.status, "is_public": o.is_public,
        "theme": {"id": o.theme.id, "name": o.theme.name} if o.theme else None,
        "reach": o.reach, "impact": o.impact, "confidence": o.confidence, "effort": o.effort,
        "priority_score": scored["priority_score"], "breakdown": scored["breakdown"],
        "metrics": {**m, "first_seen": iso(m["first_seen"]), "last_seen": iso(m["last_seen"])},
        "has_brief": o.brief is not None, "created_at": iso(o.created_at), "shipped_at": iso(o.shipped_at),
    }


@router.get("/opportunities")
def list_opportunities(ctx: WorkspaceContext = Depends(get_workspace_ctx), db: Session = Depends(get_db),
                       status_: str | None = Query(None, alias="status")):
    opps = list(db.scalars(select(Opportunity).where(Opportunity.workspace_id == ctx.id)))
    scored = score_opportunities(db, ctx.workspace, opps)
    rows = [opportunity_out(o, scored[o.id]) for o in opps if not status_ or o.status == status_]
    rows.sort(key=lambda r: -r["priority_score"])
    return {"items": rows, "weights": workspace_settings(ctx.workspace)["priority_weights"]}


@router.post("/opportunities", status_code=status.HTTP_201_CREATED)
def add_opportunity(body: OpportunityIn, ctx: WorkspaceContext = Depends(get_workspace_ctx), db: Session = Depends(get_db)):
    opp = create_opportunity(db, ctx, body)
    db.commit()
    return opportunity_out(opp, score_opportunities(db, ctx.workspace, [opp])[opp.id])


@router.get("/opportunities/{oid}")
def get_opportunity(oid: int, ctx: WorkspaceContext = Depends(get_workspace_ctx), db: Session = Depends(get_db),
                    evidence_limit: int = Query(100, ge=1, le=500)):
    opp = _get(db, ctx, oid)
    all_opps = list(db.scalars(select(Opportunity).where(Opportunity.workspace_id == ctx.id)))
    scored = score_opportunities(db, ctx.workspace, all_opps)
    rank = sorted((o for o in all_opps if o.status in ("under_review", "planned", "in_progress")),
                  key=lambda o: -scored[o.id]["priority_score"])
    linked = set(db.scalars(select(OpportunityFeedback.feedback_id).where(OpportunityFeedback.opportunity_id == oid)))
    evidence = evidence_items(db, opp)[:evidence_limit]
    decisions = db.execute(select(Decision, User.name).outerjoin(User, User.id == Decision.decided_by)
                           .where(Decision.opportunity_id == oid).order_by(Decision.created_at.desc())).all()
    notes = list(db.scalars(select(Notification.status).where(Notification.opportunity_id == oid)))
    out = opportunity_out(opp, scored[oid])
    out.update({
        "rank": next((i + 1 for i, o in enumerate(rank) if o.id == oid), None),
        "open_count": len(rank),
        "brief": opp.brief, "brief_by": opp.brief_by, "brief_at": iso(opp.brief_at),
        "evidence": [{**feedback_out(f), "linked": f.id in linked} for f in evidence],
        "decisions": [decision_out(d, opp.title, name) for d, name in decisions],
        "notifications": {"draft": notes.count("draft"), "sent": notes.count("sent"), "failed": notes.count("failed")},
    })
    return out


@router.patch("/opportunities/{oid}")
def update_opportunity(oid: int, body: OpportunityPatch, ctx: WorkspaceContext = Depends(get_workspace_ctx),
                       db: Session = Depends(get_db)):
    opp = _get(db, ctx, oid)
    data = body.model_dump(exclude_unset=True)
    loop_result = None
    if data.pop("clear_theme", False):
        opp.theme_id = None
    if data.get("theme_id") is not None:
        theme = db.get(Theme, data["theme_id"])
        if theme is None or theme.workspace_id != ctx.id:
            raise HTTPException(404, "Theme not found")
    new_status = data.pop("status", None)
    for k, v in data.items():
        if k in ("reach", "impact", "confidence", "effort") or v is not None:
            setattr(opp, k, v)
    if new_status and new_status != opp.status:
        opp.status = new_status
        if new_status == "shipped":
            opp.shipped_at = datetime.now(timezone.utc)
            db.flush()
            loop_result = on_shipped(db, ctx.workspace, opp)
    db.commit()
    db.refresh(opp)
    out = get_opportunity(oid, ctx, db, evidence_limit=100)
    out["close_the_loop"] = loop_result
    return out


@router.delete("/opportunities/{oid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_opportunity(oid: int, ctx: WorkspaceContext = Depends(get_workspace_ctx), db: Session = Depends(get_db)):
    db.delete(_get(db, ctx, oid))
    db.commit()


@router.post("/opportunities/{oid}/feedback")
def link_feedback(oid: int, body: LinkFeedbackIn, ctx: WorkspaceContext = Depends(get_workspace_ctx),
                  db: Session = Depends(get_db)):
    added = _link(db, ctx, _get(db, ctx, oid), body.feedback_ids)
    db.commit()
    return {"linked": added}


@router.delete("/opportunities/{oid}/feedback/{fid}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_feedback(oid: int, fid: int, ctx: WorkspaceContext = Depends(get_workspace_ctx), db: Session = Depends(get_db)):
    _get(db, ctx, oid)
    db.execute(delete(OpportunityFeedback).where(OpportunityFeedback.opportunity_id == oid,
                                                 OpportunityFeedback.feedback_id == fid))
    db.commit()


@router.post("/opportunities/{oid}/brief")
def generate_brief(oid: int, ctx: WorkspaceContext = Depends(get_workspace_ctx), db: Session = Depends(get_db)):
    opp = _get(db, ctx, oid)
    all_opps = list(db.scalars(select(Opportunity).where(Opportunity.workspace_id == ctx.id)))
    scored = score_opportunities(db, ctx.workspace, all_opps)[oid]
    if scored["metrics"]["mentions"] == 0 and scored["metrics"]["votes"] == 0:
        raise HTTPException(422, "No evidence yet: link feedback or a theme to this opportunity first")
    payload = brief_payload(db, ctx.workspace, opp, scored)
    ai = AIService(workspace_settings(ctx.workspace).get("ai_provider"))
    brief, by, error = ai.run("decision_brief", payload)
    opp.brief = brief.model_dump()
    opp.brief_by, opp.brief_at = by, datetime.now(timezone.utc)
    db.commit()
    return {"brief": opp.brief, "brief_by": by, "brief_at": iso(opp.brief_at), "error": error}


@router.post("/opportunities/{oid}/decisions", status_code=status.HTTP_201_CREATED)
def record_decision(oid: int, body: DecisionIn, ctx: WorkspaceContext = Depends(get_workspace_ctx),
                    db: Session = Depends(get_db)):
    opp = _get(db, ctx, oid)
    all_opps = list(db.scalars(select(Opportunity).where(Opportunity.workspace_id == ctx.id)))
    scored = score_opportunities(db, ctx.workspace, all_opps)[oid]
    m = scored["metrics"]
    snapshot = {
        "priority_score": scored["priority_score"],
        "customers": m["customers"], "mentions": m["mentions"], "mrr": m["mrr"], "votes": m["votes"],
        "avg_sentiment": m["avg_sentiment"], "churn_risk": m["churn_risk"], "countries": m["countries"],
        "ai_recommendation": (opp.brief or {}).get("recommendation"), "ai_brief_by": opp.brief_by or None,
    }
    d = Decision(workspace_id=ctx.id, opportunity_id=oid, outcome=body.outcome, rationale=body.rationale.strip(),
                 decided_by=ctx.user.id, evidence_snapshot=snapshot)
    db.add(d)
    if body.update_status and opp.status not in ("shipped",):
        opp.status = OUTCOME_STATUS[body.outcome]
    db.commit()
    return decision_out(d, opp.title, ctx.user.name)


@router.get("/decisions")
def decision_log(ctx: WorkspaceContext = Depends(get_workspace_ctx), db: Session = Depends(get_db),
                 limit: int = Query(100, ge=1, le=500)):
    rows = db.execute(
        select(Decision, Opportunity.title, User.name)
        .join(Opportunity, Opportunity.id == Decision.opportunity_id)
        .outerjoin(User, User.id == Decision.decided_by)
        .where(Decision.workspace_id == ctx.id).order_by(Decision.created_at.desc()).limit(limit)
    ).all()
    return [decision_out(d, title, name) for d, title, name in rows]
