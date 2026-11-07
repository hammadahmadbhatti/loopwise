"""Customers: who gave feedback, what they pay, how they feel."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Float, case, cast, func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import WorkspaceContext, get_workspace_ctx
from ..models import Customer, Feedback
from ..schemas import CustomerPatch, customer_out

router = APIRouter(prefix="/api/workspaces/{wid}/customers", tags=["customers"])


@router.get("")
def list_customers(
    ctx: WorkspaceContext = Depends(get_workspace_ctx),
    db: Session = Depends(get_db),
    q: str | None = None,
    sort: str = Query("mrr", pattern="^(mrr|feedback|sentiment|recent)$"),
    at_risk: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    stats = (
        select(
            Feedback.customer_id.label("cid"),
            func.count(Feedback.id).label("n"),
            func.avg(Feedback.sentiment).label("avg_sent"),
            func.sum(case((Feedback.churn_risk.is_(True), 1), else_=0)).label("churn"),
            func.max(Feedback.created_at).label("last"),
        )
        .where(Feedback.workspace_id == ctx.id, Feedback.customer_id.is_not(None))
        .group_by(Feedback.customer_id)
        .subquery()
    )
    stmt = select(Customer, stats.c.n, stats.c.avg_sent, stats.c.churn, stats.c.last).outerjoin(
        stats, stats.c.cid == Customer.id).where(Customer.workspace_id == ctx.id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Customer.email.ilike(like), Customer.name.ilike(like), Customer.company.ilike(like)))
    if at_risk:
        stmt = stmt.where(stats.c.churn > 0)
    order = {
        "mrr": Customer.mrr.desc(),
        "feedback": func.coalesce(stats.c.n, 0).desc(),
        "sentiment": func.coalesce(cast(stats.c.avg_sent, Float), 0).asc(),
        "recent": stats.c.last.desc(),
    }[sort]
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(stmt.order_by(order, Customer.id).offset((page - 1) * page_size).limit(page_size)).all()
    return {
        "total": total,
        "items": [
            {**customer_out(c), "feedback_count": n or 0,
             "avg_sentiment": round(float(s), 3) if s is not None else None, "churn_signals": int(ch or 0)}
            for c, n, s, ch, _ in rows
        ],
    }


@router.patch("/{cid}")
def update_customer(cid: int, body: CustomerPatch, ctx: WorkspaceContext = Depends(get_workspace_ctx),
                    db: Session = Depends(get_db)):
    c = db.get(Customer, cid)
    if c is None or c.workspace_id != ctx.id:
        raise HTTPException(404, "Customer not found")
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(c, k, v)
    db.commit()
    return customer_out(c)
