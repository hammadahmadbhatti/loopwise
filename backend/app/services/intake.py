"""Single entry point for new feedback, whatever channel it arrives through."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Customer, Feedback, Workspace

MAX_TEXT = 10_000


def upsert_customer(
    db: Session,
    workspace_id: int,
    *,
    email: str | None = None,
    name: str | None = None,
    company: str | None = None,
    country: str | None = None,
    plan: str | None = None,
    mrr: float | None = None,
    external_id: str | None = None,
) -> Customer | None:
    """Find a customer by email (or external id) and fill in any new attributes."""
    email = (email or "").strip().lower() or None
    external_id = (external_id or "").strip() or None
    if not email and not external_id:
        return None
    customer = None
    if email:
        customer = db.scalar(select(Customer).where(Customer.workspace_id == workspace_id, Customer.email == email))
    if customer is None and external_id:
        customer = db.scalar(
            select(Customer).where(Customer.workspace_id == workspace_id, Customer.external_id == external_id)
        )
    if customer is None:
        customer = Customer(workspace_id=workspace_id, email=email, external_id=external_id or "")
        db.add(customer)
    updates = {"name": name, "company": company, "country": country, "plan": plan}
    for field, value in updates.items():
        if value and str(value).strip():
            setattr(customer, field, str(value).strip()[:200])
    if mrr is not None and mrr >= 0:
        customer.mrr = float(mrr)
    if email and not customer.email:
        customer.email = email
    db.flush()
    return customer


def create_feedback(
    db: Session,
    ws: Workspace,
    *,
    text: str,
    source: str,
    customer: Customer | None = None,
    rating: int | None = None,
    country: str | None = None,
    page_url: str | None = None,
    created_at: datetime | None = None,
    meta: dict[str, Any] | None = None,
) -> Feedback:
    text = (text or "").strip()
    if not text:
        raise ValueError("Feedback text is empty")
    if rating is not None and not 1 <= int(rating) <= 5:
        rating = None
    fb = Feedback(
        workspace_id=ws.id,
        customer_id=customer.id if customer else None,
        source=source,
        text=text[:MAX_TEXT],
        rating=int(rating) if rating is not None else None,
        country=(country or (customer.country if customer else "") or "").strip()[:80],
        page_url=(page_url or "")[:1000],
        meta=meta or {},
        created_at=created_at or datetime.now(timezone.utc),
        analysis_status="pending",
    )
    db.add(fb)
    db.flush()
    return fb
