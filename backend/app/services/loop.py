"""Closing the loop: when an opportunity ships, tell every customer who asked for it, in their language.

Shipping creates a changelog draft and one notification draft per affected
customer. Nothing is emailed until a team member reviews and sends, either
through SMTP or (by default) to an outbox folder of .eml files.
"""

from __future__ import annotations

import logging
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.base import Message
from ..ai.heuristic import HeuristicProvider
from ..ai.registry import AIService
from ..config import get_settings
from ..deps import workspace_settings
from ..models import ChangelogEntry, Customer, Notification, Opportunity, Vote, Workspace
from .scoring import evidence_items

log = logging.getLogger("loopwise.loop")


def affected_customers(db: Session, opp: Opportunity) -> list[Customer]:
    by_id: dict[int, Customer] = {}
    for f in evidence_items(db, opp):
        if f.customer and f.customer.email:
            by_id[f.customer.id] = f.customer
    voter_ids = list(db.scalars(select(Vote.customer_id).where(Vote.opportunity_id == opp.id)))
    if voter_ids:
        for c in db.scalars(select(Customer).where(Customer.id.in_(voter_ids))):
            if c.email:
                by_id[c.id] = c
    return sorted(by_id.values(), key=lambda c: c.id)


def _personalize(text: str, customer: Customer) -> str:
    first = (customer.name or "").split(" ")[0] or "there"
    return text.replace("{{name}}", first)


def changelog_body(db: Session, opp: Opportunity) -> str:
    """Public changelog text: what changed plus who asked for it (draft; the team edits before publishing)."""
    items = [f for f in evidence_items(db, opp) if f.duplicate_of_id is None]
    people = {f.customer_id or -f.id for f in items}
    countries = {(f.country or (f.customer.country if f.customer else "")).strip() for f in items} - {""}
    votes = len(list(db.scalars(select(Vote.id).where(Vote.opportunity_id == opp.id))))
    parts = [opp.description.strip()] if opp.description.strip() else [f"{opp.title} is now available."]
    credit = f"Shipped thanks to feedback from {len(people)} customer{'s' if len(people) != 1 else ''}"
    if len(countries) > 1:
        credit += f" in {len(countries)} countries"
    if votes:
        credit += f" and {votes} vote{'s' if votes != 1 else ''} on our roadmap"
    parts.append(credit + ". Thank you for telling us what matters.")
    return "\n\n".join(parts)


def on_shipped(db: Session, ws: Workspace, opp: Opportunity) -> dict:
    """Create the changelog draft and localized notification drafts. Idempotent per customer."""
    settings = workspace_settings(ws)
    working = settings.get("working_language", "en")
    ai = AIService(settings.get("ai_provider"))
    payload = {"title": opp.title, "description": opp.description, "company": ws.name, "language": working,
               "theme": opp.theme.name if opp.theme else None}
    base, written_by, _ = ai.run("release_note", payload)

    entry = db.scalar(select(ChangelogEntry).where(ChangelogEntry.opportunity_id == opp.id))
    if entry is None:
        entry = ChangelogEntry(workspace_id=ws.id, opportunity_id=opp.id, title=opp.title,
                               body=changelog_body(db, opp), written_by="loopwise:opportunity")
        db.add(entry)

    existing = {n.customer_id for n in db.scalars(select(Notification).where(Notification.opportunity_id == opp.id))}
    customers = [c for c in affected_customers(db, opp) if c.id not in existing]
    offline = HeuristicProvider()
    localized: dict[str, tuple[Message, str]] = {working: (base, written_by)}
    created = 0
    for c in customers:
        lang = (c.language or working).split("-")[0]
        if lang not in localized:
            if ai.is_offline:
                msg, by = offline.release_note({**payload, "language": lang}), offline.label + " (template)"
                if not offline.supports_template_language(lang):
                    msg, by = base, offline.label + " (no template, sent in working language)"
            else:
                msg, by, err = ai.run("localize", base, lang)
                if err:  # provider failed and offline engine can't translate: use its templates
                    msg = offline.release_note({**payload, "language": lang})
                    by = offline.label + " (template fallback)"
            localized[lang] = (msg, by)
        msg, by = localized[lang]
        db.add(Notification(
            workspace_id=ws.id, opportunity_id=opp.id, customer_id=c.id, email=c.email or "",
            language=lang, subject=_personalize(msg.subject, c)[:300], body=_personalize(msg.body, c),
            status="draft", localized_by=by,
        ))
        created += 1
    db.flush()
    return {"changelog_entry_id": entry.id, "notifications_created": created, "languages": sorted(localized)}


def deliver(db: Session, ws: Workspace, notifications: list[Notification]) -> dict:
    settings = get_settings()
    sent = failed = 0
    smtp = None
    try:
        if settings.email_mode == "smtp":
            if not settings.smtp_host:
                raise RuntimeError("EMAIL_MODE=smtp but SMTP_HOST is not set")
            smtp = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30)
            if settings.smtp_starttls:
                smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password or "")
        outbox = Path(settings.outbox_dir) / f"workspace-{ws.id}"
        for n in notifications:
            if n.status == "sent":
                continue
            msg = EmailMessage()
            msg["From"] = settings.smtp_from
            msg["To"] = n.email
            msg["Subject"] = n.subject
            msg.set_content(n.body)
            msg["Content-Language"] = n.language  # after set_content(), which resets Content-* headers
            try:
                if smtp is not None:
                    smtp.send_message(msg)
                    n.channel = "smtp"
                else:
                    outbox.mkdir(parents=True, exist_ok=True)
                    (outbox / f"notification-{n.id}.eml").write_bytes(bytes(msg))
                    n.channel = "outbox"
                n.status, n.error, n.sent_at = "sent", "", datetime.now(timezone.utc)
                sent += 1
            except (smtplib.SMTPException, OSError) as exc:
                n.status, n.error = "failed", str(exc)[:500]
                failed += 1
    finally:
        if smtp is not None:
            try:
                smtp.quit()
            except smtplib.SMTPException:  # pragma: no cover
                pass
    db.flush()
    return {"sent": sent, "failed": failed, "mode": settings.email_mode}
