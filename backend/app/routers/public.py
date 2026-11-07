"""Unauthenticated endpoints: website widget, public feedback portal, server-to-server API."""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..deps import get_workspace_by_api_key, workspace_settings
from ..models import ChangelogEntry, Opportunity, Vote, Workspace
from ..schemas import ApiFeedbackIn, InboundEmailIn, PublicFeedbackIn, VoteIn, iso
from ..services.intake import create_feedback, upsert_customer

router = APIRouter(tags=["public"])
_hits: dict[str, deque] = defaultdict(deque)


def rate_limit(request: Request) -> None:
    """Simple sliding-window limiter per client IP and path (in-memory; use Redis when running several replicas)."""
    settings = get_settings()
    ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "?")
    key = f"{ip}|{request.url.path}"
    now = time.monotonic()
    q = _hits[key]
    while q and now - q[0] > settings.public_rate_window_seconds:
        q.popleft()
    if len(q) >= settings.public_rate_limit:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests, please try again later")
    q.append(now)


def _portal_ws(db: Session, slug: str) -> Workspace:
    ws = db.scalar(select(Workspace).where(Workspace.slug == slug))
    if ws is None or not workspace_settings(ws).get("portal_enabled", True):
        raise HTTPException(404, "Portal not found")
    return ws


@router.get("/api/public/portal/{slug}")
def portal(slug: str, db: Session = Depends(get_db)):
    ws = _portal_ws(db, slug)
    settings = workspace_settings(ws)
    votes = dict(db.execute(select(Vote.opportunity_id, func.count()).group_by(Vote.opportunity_id)).all())
    opps = db.scalars(select(Opportunity).where(Opportunity.workspace_id == ws.id, Opportunity.is_public.is_(True),
                                                Opportunity.status != "declined").order_by(Opportunity.created_at.desc()))
    entries = db.scalars(select(ChangelogEntry).where(ChangelogEntry.workspace_id == ws.id, ChangelogEntry.published.is_(True))
                         .order_by(ChangelogEntry.published_at.desc()).limit(30))
    return {
        "name": ws.name, "title": settings.get("portal_title") or f"{ws.name} feedback", "brand_color": settings["brand_color"],
        "public_key": ws.public_key,
        "roadmap": [{"id": o.id, "title": o.title, "description": o.description, "status": o.status,
                     "votes": votes.get(o.id, 0), "shipped_at": iso(o.shipped_at)} for o in opps],
        "changelog": [{"id": e.id, "title": e.title, "body": e.body, "published_at": iso(e.published_at)} for e in entries],
    }


@router.post("/api/public/portal/{slug}/feedback", status_code=201, dependencies=[Depends(rate_limit)])
def portal_feedback(slug: str, body: PublicFeedbackIn, db: Session = Depends(get_db)):
    ws = _portal_ws(db, slug)
    return _accept(db, ws, body, "portal")


@router.post("/api/public/portal/{slug}/opportunities/{oid}/vote", dependencies=[Depends(rate_limit)])
def vote(slug: str, oid: int, body: VoteIn, db: Session = Depends(get_db)):
    ws = _portal_ws(db, slug)
    opp = db.get(Opportunity, oid)
    if opp is None or opp.workspace_id != ws.id or not opp.is_public:
        raise HTTPException(404, "Not found")
    customer = upsert_customer(db, ws.id, email=body.email, name=body.name)
    already = db.scalar(select(Vote).where(Vote.opportunity_id == oid, Vote.customer_id == customer.id))
    if already is None:
        db.add(Vote(opportunity_id=oid, customer_id=customer.id))
    db.commit()
    count = db.scalar(select(func.count()).select_from(Vote).where(Vote.opportunity_id == oid))
    return {"votes": count, "already_voted": already is not None}


@router.post("/api/public/widget/{public_key}/feedback", status_code=201, dependencies=[Depends(rate_limit)])
def widget_feedback(public_key: str, body: PublicFeedbackIn, db: Session = Depends(get_db)):
    ws = db.scalar(select(Workspace).where(Workspace.public_key == public_key))
    if ws is None:
        raise HTTPException(404, "Unknown widget key")
    return _accept(db, ws, body, "widget")


def _accept(db: Session, ws: Workspace, body: PublicFeedbackIn, source: str) -> dict:
    if body.website:  # honeypot field filled: almost certainly a bot; pretend success
        return {"ok": True}
    customer = upsert_customer(db, ws.id, email=body.email, name=body.name) if body.email else None
    meta = {k: str(v)[:200] for k, v in (body.meta or {}).items()}
    create_feedback(db, ws, text=body.text, source=source, customer=customer, rating=body.rating,
                    page_url=body.page_url, meta=meta)
    db.commit()
    return {"ok": True}


@router.post("/api/v1/feedback", status_code=201, tags=["ingest API"])
def api_ingest(body: ApiFeedbackIn, ws: Workspace = Depends(get_workspace_by_api_key), db: Session = Depends(get_db)):
    """Server-to-server ingestion (CRM, support desk, app backend). Authenticate with the X-API-Key header."""
    customer = upsert_customer(db, ws.id, email=body.email, name=body.name, company=body.company,
                               country=body.country, plan=body.plan, mrr=body.mrr, external_id=body.external_id)
    fb = create_feedback(db, ws, text=body.text, source=body.source, customer=customer, rating=body.rating,
                         country=body.country, created_at=body.created_at)
    db.commit()
    return {"id": fb.id, "analysis_status": fb.analysis_status}


@router.post("/api/v1/inbound-email", status_code=201, tags=["ingest API"])
def inbound_email(body: InboundEmailIn, ws: Workspace = Depends(get_workspace_by_api_key), db: Session = Depends(get_db)):
    """Point an inbound-email webhook (SendGrid Inbound Parse, Postmark, Mailgun routes) here."""
    customer = upsert_customer(db, ws.id, email=body.from_email, name=body.from_name)
    text = f"{body.subject.strip()}\n\n{body.text.strip()}" if body.subject.strip() else body.text.strip()
    fb = create_feedback(db, ws, text=text, source="email", customer=customer, meta={"subject": body.subject[:300]})
    db.commit()
    return {"id": fb.id}
