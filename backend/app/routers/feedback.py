"""Feedback inbox: list/filter, detail, manual entry, CSV import/export, triage."""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import false, func, or_, select
from sqlalchemy.orm import Session

from ..ai.embeddings import cosine, get_embedder
from ..db import get_db
from ..deps import WorkspaceContext, get_workspace_ctx
from ..models import Customer, Feedback, Opportunity, OpportunityFeedback, Theme
from ..schemas import FeedbackIn, FeedbackPatch, feedback_out, iso
from ..services.importer import import_csv
from ..services.intake import create_feedback, upsert_customer
from ..services.themes import ensure_embeddings

router = APIRouter(prefix="/api/workspaces/{wid}/feedback", tags=["feedback"])
MAX_UPLOAD = 10 * 1024 * 1024


def _get(db: Session, ctx: WorkspaceContext, fid: int) -> Feedback:
    fb = db.get(Feedback, fid)
    if fb is None or fb.workspace_id != ctx.id:
        raise HTTPException(404, "Feedback not found")
    return fb


@router.get("")
def list_feedback(
    ctx: WorkspaceContext = Depends(get_workspace_ctx),
    db: Session = Depends(get_db),
    q: str | None = None,
    sentiment: str | None = Query(None, pattern="^(positive|neutral|negative)$"),
    category: str | None = None,
    urgency: str | None = None,
    language: str | None = None,
    source: str | None = None,
    status_: str | None = Query(None, alias="status"),
    theme_id: int | None = None,
    unthemed: bool = False,
    churn_risk: bool | None = None,
    country: str | None = None,
    customer_id: int | None = None,
    sort: str = Query("newest", pattern="^(newest|oldest|most_negative|highest_mrr)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    stmt = select(Feedback).where(Feedback.workspace_id == ctx.id)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Feedback.text.ilike(like), Feedback.translated_text.ilike(like), Feedback.summary.ilike(like)))
    filters = {Feedback.sentiment_label: sentiment, Feedback.category: category, Feedback.urgency: urgency,
               Feedback.language: language, Feedback.source: source, Feedback.theme_id: theme_id,
               Feedback.customer_id: customer_id}
    for col, val in filters.items():
        if val is not None and val != "":
            stmt = stmt.where(col == val)
    if status_:
        stmt = stmt.where(Feedback.status == status_)
    else:
        stmt = stmt.where(Feedback.status != "archived")
    if unthemed:
        stmt = stmt.where(Feedback.theme_id.is_(None), Feedback.analysis_status == "done")
    if churn_risk is not None:
        stmt = stmt.where(Feedback.churn_risk.is_(churn_risk))
    if country:
        stmt = stmt.where(Feedback.country == country)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    if sort == "oldest":
        stmt = stmt.order_by(Feedback.created_at.asc())
    elif sort == "most_negative":
        stmt = stmt.order_by(Feedback.sentiment.is_(None), Feedback.sentiment.asc())
    elif sort == "highest_mrr":
        stmt = stmt.outerjoin(Customer, Customer.id == Feedback.customer_id).order_by(func.coalesce(Customer.mrr, 0).desc(), Feedback.created_at.desc())
    else:
        stmt = stmt.order_by(Feedback.created_at.desc(), Feedback.id.desc())
    rows = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).unique().all()
    facets = {
        "languages": [r for r in db.scalars(select(Feedback.language).where(Feedback.workspace_id == ctx.id, Feedback.language != "").distinct())],
        "countries": [r for r in db.scalars(select(Feedback.country).where(Feedback.workspace_id == ctx.id, Feedback.country != "").distinct())],
    }
    return {"items": [feedback_out(f) for f in rows], "total": total, "page": page, "page_size": page_size, "facets": facets}


@router.post("", status_code=status.HTTP_201_CREATED)
def add_feedback(body: FeedbackIn, ctx: WorkspaceContext = Depends(get_workspace_ctx), db: Session = Depends(get_db)):
    customer = None
    if body.customer:
        customer = upsert_customer(db, ctx.id, **body.customer.model_dump())
    fb = create_feedback(db, ctx.workspace, text=body.text, source=body.source, customer=customer,
                         rating=body.rating, country=body.country, created_at=body.created_at)
    db.commit()
    return feedback_out(fb)


@router.post("/import")
async def import_feedback(file: UploadFile = File(...), ctx: WorkspaceContext = Depends(get_workspace_ctx),
                          db: Session = Depends(get_db)):
    raw = await file.read(MAX_UPLOAD + 1)
    if len(raw) > MAX_UPLOAD:
        raise HTTPException(413, "CSV larger than 10 MB; split it into smaller files")
    try:
        return import_csv(db, ctx.workspace, raw)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/export.csv")
def export_csv(ctx: WorkspaceContext = Depends(get_workspace_ctx), db: Session = Depends(get_db)):
    rows = db.scalars(select(Feedback).where(Feedback.workspace_id == ctx.id).order_by(Feedback.created_at)).unique()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "created_at", "source", "text", "translated_text", "language", "sentiment", "sentiment_label",
                "category", "urgency", "churn_risk", "theme", "customer_email", "company", "plan", "mrr", "country"])
    for f in rows:
        c = f.customer
        w.writerow([f.id, iso(f.created_at), f.source, f.text, f.translated_text, f.language, f.sentiment,
                    f.sentiment_label, f.category, f.urgency, f.churn_risk, f.theme.name if f.theme else "",
                    c.email if c else "", c.company if c else "", c.plan if c else "", c.mrr if c else "",
                    f.country])
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=feedback.csv"})


@router.get("/{fid}")
def get_feedback(fid: int, ctx: WorkspaceContext = Depends(get_workspace_ctx), db: Session = Depends(get_db)):
    fb = _get(db, ctx, fid)
    out = feedback_out(fb)
    opps = db.execute(
        select(Opportunity.id, Opportunity.title, Opportunity.status)
        .where(Opportunity.workspace_id == ctx.id,
               or_(Opportunity.id.in_(select(OpportunityFeedback.opportunity_id).where(OpportunityFeedback.feedback_id == fid)),
                   (Opportunity.theme_id == fb.theme_id) if fb.theme_id else false()))
    ).all()
    out["opportunities"] = [{"id": i, "title": t, "status": s} for i, t, s in opps]
    out["similar"] = []
    if fb.analysis_status == "done":
        embedder = get_embedder()
        pool = list(db.scalars(select(Feedback).where(Feedback.workspace_id == ctx.id, Feedback.id != fid,
                                                      Feedback.analysis_status == "done")
                               .order_by(Feedback.created_at.desc()).limit(1000)).unique())
        if pool:
            ensure_embeddings(db, [fb, *pool], embedder)
            db.commit()
            X = embedder.matrix([fb.embedding] + [p.embedding for p in pool])
            sims = cosine(X[0], X[1:]).ravel()
            best = sorted(range(len(pool)), key=lambda i: -sims[i])[:5]
            out["similar"] = [{"id": pool[i].id, "summary": pool[i].summary or pool[i].text[:160],
                               "similarity": round(float(sims[i]), 3), "language": pool[i].language}
                              for i in best if sims[i] > embedder.retrieval_min]
    return out


@router.patch("/{fid}")
def update_feedback(fid: int, body: FeedbackPatch, ctx: WorkspaceContext = Depends(get_workspace_ctx),
                    db: Session = Depends(get_db)):
    fb = _get(db, ctx, fid)
    if body.status:
        fb.status = body.status
    if body.clear_theme:
        fb.theme_id, fb.theme_locked = None, True
    elif body.theme_id is not None:
        theme = db.get(Theme, body.theme_id)
        if theme is None or theme.workspace_id != ctx.id:
            raise HTTPException(404, "Theme not found")
        fb.theme_id, fb.theme_locked = theme.id, True
        theme.archived = False
    if body.category:
        fb.category = body.category
    db.commit()
    db.refresh(fb)
    return feedback_out(fb)


@router.post("/{fid}/reanalyze")
def reanalyze(fid: int, ctx: WorkspaceContext = Depends(get_workspace_ctx), db: Session = Depends(get_db)):
    fb = _get(db, ctx, fid)
    fb.analysis_status, fb.analysis_attempts, fb.analysis_error = "pending", 0, ""
    db.commit()
    return feedback_out(fb)


@router.post("/reanalyze-all")
def reanalyze_all(ctx: WorkspaceContext = Depends(get_workspace_ctx), db: Session = Depends(get_db)):
    """Re-run analysis for everything, e.g. after switching from the offline engine to Claude."""
    items = db.scalars(select(Feedback).where(Feedback.workspace_id == ctx.id)).unique().all()
    for fb in items:
        fb.analysis_status, fb.analysis_attempts, fb.analysis_error = "pending", 0, ""
    db.commit()
    return {"queued": len(items)}


@router.delete("/{fid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_feedback(fid: int, ctx: WorkspaceContext = Depends(get_workspace_ctx), db: Session = Depends(get_db)):
    db.delete(_get(db, ctx, fid))
    db.commit()
