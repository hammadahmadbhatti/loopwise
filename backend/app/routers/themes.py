"""Themes discovered from feedback: list with trends, rename, merge, re-run discovery."""

from __future__ import annotations

from collections import Counter, defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import WorkspaceContext, get_workspace_ctx
from ..models import Feedback, Opportunity, Theme
from ..schemas import MergeIn, OpportunityIn, ThemePatch, feedback_out, iso
from ..services.insights import theme_trends
from ..services.themes import discover_themes
from .opportunities import create_opportunity

router = APIRouter(prefix="/api/workspaces/{wid}/themes", tags=["themes"])


def _get(db: Session, ctx: WorkspaceContext, tid: int) -> Theme:
    t = db.get(Theme, tid)
    if t is None or t.workspace_id != ctx.id:
        raise HTTPException(404, "Theme not found")
    return t


@router.get("")
def list_themes(ctx: WorkspaceContext = Depends(get_workspace_ctx), db: Session = Depends(get_db),
                include_archived: bool = False):
    themes = list(db.scalars(select(Theme).where(Theme.workspace_id == ctx.id)))
    items = list(db.scalars(select(Feedback).where(Feedback.workspace_id == ctx.id, Feedback.theme_id.is_not(None),
                                                   Feedback.duplicate_of_id.is_(None), Feedback.status != "archived")).unique())
    by_theme: dict[int, list[Feedback]] = defaultdict(list)
    for f in items:
        by_theme[f.theme_id].append(f)
    trends = theme_trends(db, ctx.id)
    opps = defaultdict(list)
    for oid, title, status, tid in db.execute(select(Opportunity.id, Opportunity.title, Opportunity.status, Opportunity.theme_id)
                                              .where(Opportunity.workspace_id == ctx.id, Opportunity.theme_id.is_not(None))):
        opps[tid].append({"id": oid, "title": title, "status": status})
    out = []
    for t in themes:
        members = by_theme.get(t.id, [])
        if t.archived and not include_archived:
            continue
        sents = [f.sentiment for f in members if f.sentiment is not None]
        customers = {f.customer_id for f in members if f.customer_id}
        out.append({
            "id": t.id, "name": t.name, "description": t.description, "keywords": t.keywords,
            "archived": t.archived, "name_locked": t.name_locked, "labeled_by": t.labeled_by,
            "count": len(members), "customers": len(customers),
            "mrr": round(sum({f.customer_id: f.customer.mrr or 0 for f in members if f.customer}.values()), 2),
            "avg_sentiment": round(sum(sents) / len(sents), 3) if sents else None,
            "negative_pct": round(100 * sum(1 for s in sents if s < -0.2) / len(sents)) if sents else 0,
            "churn_risk": sum(1 for f in members if f.churn_risk),
            "categories": Counter(f.category for f in members if f.category).most_common(3),
            "languages": [lang for lang, _ in Counter(f.language for f in members if f.language).most_common(5)],
            "countries": sorted({f.country for f in members if f.country}),
            "weekly": trends.get(t.id, {}).get("weekly", [0] * 8),
            "emerging": trends.get(t.id, {}).get("emerging", False),
            "opportunities": opps.get(t.id, []),
            "updated_at": iso(t.updated_at),
        })
    unthemed = db.scalar(select(Feedback.id).where(Feedback.workspace_id == ctx.id, Feedback.theme_id.is_(None),
                                                   Feedback.analysis_status == "done").limit(1))
    out.sort(key=lambda r: (-r["count"], r["name"]))
    return {"items": out, "has_unthemed": unthemed is not None}


@router.post("/discover")
def rediscover(ctx: WorkspaceContext = Depends(get_workspace_ctx), db: Session = Depends(get_db)):
    summary = discover_themes(db, ctx.workspace)
    db.commit()
    return summary


@router.get("/{tid}")
def get_theme(tid: int, ctx: WorkspaceContext = Depends(get_workspace_ctx), db: Session = Depends(get_db)):
    t = _get(db, ctx, tid)
    items = db.scalars(select(Feedback).where(Feedback.theme_id == t.id).order_by(Feedback.created_at.desc()).limit(200)).unique().all()
    return {"id": t.id, "name": t.name, "description": t.description, "keywords": t.keywords,
            "archived": t.archived, "labeled_by": t.labeled_by, "feedback": [feedback_out(f) for f in items]}


@router.patch("/{tid}")
def rename_theme(tid: int, body: ThemePatch, ctx: WorkspaceContext = Depends(get_workspace_ctx), db: Session = Depends(get_db)):
    t = _get(db, ctx, tid)
    if body.name:
        t.name, t.name_locked = body.name.strip(), True
    if body.description is not None:
        t.description = body.description
    db.commit()
    return {"id": t.id, "name": t.name, "description": t.description, "name_locked": t.name_locked}


@router.post("/{tid}/merge")
def merge_theme(tid: int, body: MergeIn, ctx: WorkspaceContext = Depends(get_workspace_ctx), db: Session = Depends(get_db)):
    source, target = _get(db, ctx, tid), _get(db, ctx, body.into_id)
    if source.id == target.id:
        raise HTTPException(422, "Cannot merge a theme into itself")
    moved = db.execute(update(Feedback).where(Feedback.theme_id == source.id)
                       .values(theme_id=target.id, theme_locked=True)).rowcount
    db.execute(update(Opportunity).where(Opportunity.theme_id == source.id).values(theme_id=target.id))
    source.archived = True
    target.archived = False
    db.commit()
    return {"merged_into": target.id, "moved_feedback": moved}


@router.post("/{tid}/opportunity", status_code=201)
def opportunity_from_theme(tid: int, ctx: WorkspaceContext = Depends(get_workspace_ctx), db: Session = Depends(get_db)):
    t = _get(db, ctx, tid)
    existing = db.scalar(select(Opportunity).where(Opportunity.theme_id == t.id, Opportunity.workspace_id == ctx.id))
    if existing:
        return {"id": existing.id, "existing": True}
    opp = create_opportunity(db, ctx, OpportunityIn(title=t.name, description=t.description, theme_id=t.id))
    db.commit()
    return {"id": opp.id, "existing": False}
