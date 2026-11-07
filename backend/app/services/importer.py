"""CSV import (survey exports, app-store reviews, support-tool exports...).

Columns are matched by common names, case-insensitively. Only a text column is required.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from ..models import Workspace
from .intake import create_feedback, upsert_customer

MAX_ROWS = 20_000
ALIASES: dict[str, tuple[str, ...]] = {
    "text": ("text", "feedback", "comment", "comments", "message", "review", "body", "content", "response", "verbatim"),
    "email": ("email", "customer_email", "user_email", "e-mail", "mail"),
    "name": ("name", "customer_name", "customer", "user", "author", "full_name"),
    "company": ("company", "account", "organization", "organisation", "company_name"),
    "country": ("country", "country_code", "region", "location"),
    "plan": ("plan", "tier", "subscription", "segment"),
    "mrr": ("mrr", "monthly_revenue", "revenue"),
    "arr": ("arr", "annual_revenue"),
    "rating": ("rating", "stars", "score", "csat"),
    "created_at": ("created_at", "date", "timestamp", "created", "submitted_at", "time"),
    "source": ("source", "channel", "origin"),
    "external_id": ("customer_id", "user_id", "external_id", "account_id"),
}
DATE_FORMATS = ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%d.%m.%Y", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d")


def _map_columns(headers: list[str]) -> dict[str, str]:
    lowered = {h.strip().lower().replace(" ", "_"): h for h in headers if h}
    mapping = {}
    for field, names in ALIASES.items():
        for n in names:
            if n in lowered:
                mapping[field] = lowered[n]
                break
    return mapping


def _parse_date(value: str) -> datetime | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _num(value: str) -> float | None:
    try:
        return float(str(value).replace(",", "").replace("$", "").replace("€", "").strip())
    except (TypeError, ValueError):
        return None


def import_csv(db: Session, ws: Workspace, raw: bytes) -> dict[str, Any]:
    text = raw.decode("utf-8-sig", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    mapping = _map_columns(reader.fieldnames or [])
    if "text" not in mapping:
        raise ValueError(
            "No feedback text column found. Name one of the columns: " + ", ".join(ALIASES["text"])
        )
    rows = list(reader)
    # A rating column with any value above 5 is a 0-10 (NPS-style) scale: map the whole column to 1-5
    ten_scale = "rating" in mapping and any((_num(r.get(mapping["rating"]) or "") or 0) > 5 for r in rows)
    imported, skipped, errors = 0, 0, []
    for line_no, row in enumerate(rows, start=2):
        if imported + skipped >= MAX_ROWS:
            errors.append(f"Stopped after {MAX_ROWS} rows")
            break
        get = lambda f: (row.get(mapping[f]) or "").strip() if f in mapping else ""  # noqa: E731
        body = get("text")
        if not body:
            skipped += 1
            continue
        mrr = _num(get("mrr"))
        if mrr is None and get("arr"):
            arr = _num(get("arr"))
            mrr = arr / 12 if arr is not None else None
        rating = _num(get("rating"))
        if rating is not None and ten_scale:
            rating = max(1, min(5, round(rating / 2)))
        if rating is not None and not 1 <= rating <= 5:
            rating = None
        try:
            customer = upsert_customer(db, ws.id, email=get("email"), name=get("name"), company=get("company"),
                                       country=get("country"), plan=get("plan"), mrr=mrr,
                                       external_id=get("external_id"))
            create_feedback(db, ws, text=body, source=(get("source") or "import")[:30], customer=customer,
                            rating=int(rating) if rating else None, country=get("country"),
                            created_at=_parse_date(get("created_at")), meta={"import_line": line_no})
            imported += 1
        except ValueError as exc:
            skipped += 1
            errors.append(f"Line {line_no}: {exc}")
    db.commit()
    return {"imported": imported, "skipped": skipped, "errors": errors[:20], "columns": mapping}
