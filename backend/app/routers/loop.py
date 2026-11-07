"""Close the loop: changelog and customer notifications (review, edit, send)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..deps import WorkspaceContext, get_workspace_ctx, require_admin
from ..models import ChangelogEntry, Notification, Opportunity
from ..schemas import ChangelogIn, ChangelogPatch, NotificationPatch, SendIn, changelog_out, notification_out
from ..services.loop import deliver

router = APIRouter(prefix="/api/workspaces/{wid}", tags=["close the loop"])


def _entry(db: Session, ctx: WorkspaceContext, eid: int) -> ChangelogEntry:
    e = db.get(ChangelogEntry, eid)
    if e is None or e.workspace_id != ctx.id:
        raise HTTPException(404, "Changelog entry not found")
    return e


@router.get("/changelog")
def list_changelog(ctx: WorkspaceContext = Depends(get_workspace_ctx), db: Session = Depends(get_db)):
    rows = db.scalars(select(ChangelogEntry).where(ChangelogEntry.workspace_id == ctx.id)
                      .order_by(ChangelogEntry.created_at.desc()))
    return [changelog_out(e) for e in rows]


@router.post("/changelog", status_code=status.HTTP_201_CREATED)
def add_changelog(body: ChangelogIn, ctx: WorkspaceContext = Depends(get_workspace_ctx), db: Session = Depends(get_db)):
    e = ChangelogEntry(workspace_id=ctx.id, title=body.title, body=body.body, published=body.published,
                       published_at=datetime.now(timezone.utc) if body.published else None, written_by=ctx.user.email)
    db.add(e)
    db.commit()
    return changelog_out(e)


@router.patch("/changelog/{eid}")
def update_changelog(eid: int, body: ChangelogPatch, ctx: WorkspaceContext = Depends(get_workspace_ctx),
                     db: Session = Depends(get_db)):
    e = _entry(db, ctx, eid)
    if body.title is not None:
        e.title = body.title
    if body.body is not None:
        e.body = body.body
    if body.published is not None and body.published != e.published:
        e.published = body.published
        e.published_at = datetime.now(timezone.utc) if body.published else None
    db.commit()
    return changelog_out(e)


@router.delete("/changelog/{eid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_changelog(eid: int, ctx: WorkspaceContext = Depends(get_workspace_ctx), db: Session = Depends(get_db)):
    db.delete(_entry(db, ctx, eid))
    db.commit()


@router.get("/notifications")
def list_notifications(ctx: WorkspaceContext = Depends(get_workspace_ctx), db: Session = Depends(get_db),
                       status_: str | None = Query(None, alias="status"), opportunity_id: int | None = None):
    stmt = select(Notification, Opportunity.title).outerjoin(Opportunity, Opportunity.id == Notification.opportunity_id)\
        .where(Notification.workspace_id == ctx.id)
    if status_:
        stmt = stmt.where(Notification.status == status_)
    if opportunity_id:
        stmt = stmt.where(Notification.opportunity_id == opportunity_id)
    rows = db.execute(stmt.order_by(Notification.created_at.desc()).limit(500)).all()
    settings = get_settings()
    return {
        "items": [{**notification_out(n), "opportunity_title": title} for n, title in rows],
        "delivery": {"mode": settings.email_mode,
                     "detail": "Emails are written as .eml files to the outbox folder" if settings.email_mode != "smtp"
                     else f"Sending through {settings.smtp_host}"},
    }


@router.patch("/notifications/{nid}")
def edit_notification(nid: int, body: NotificationPatch, ctx: WorkspaceContext = Depends(get_workspace_ctx),
                      db: Session = Depends(get_db)):
    n = db.get(Notification, nid)
    if n is None or n.workspace_id != ctx.id:
        raise HTTPException(404, "Notification not found")
    if n.status == "sent":
        raise HTTPException(409, "Already sent")
    if body.subject is not None:
        n.subject = body.subject
    if body.body is not None:
        n.body = body.body
    db.commit()
    return notification_out(n)


@router.post("/notifications/send")
def send_notifications(body: SendIn, ctx: WorkspaceContext = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(Notification).where(Notification.workspace_id == ctx.id, Notification.status.in_(("draft", "failed")))
    if body.notification_ids:
        stmt = stmt.where(Notification.id.in_(body.notification_ids))
    elif body.opportunity_id:
        stmt = stmt.where(Notification.opportunity_id == body.opportunity_id)
    else:
        raise HTTPException(422, "Pass notification_ids or opportunity_id")
    items = list(db.scalars(stmt))
    result = deliver(db, ctx.workspace, items)
    db.commit()
    return result
