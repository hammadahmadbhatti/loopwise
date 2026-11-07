"""Request bodies and shared serializers for API responses."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from .models import ChangelogEntry, Customer, Decision, Feedback, Notification, Theme

# ---------------------------------------------------------------- requests


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    name: str = Field(default="", max_length=200)
    workspace_name: str = Field(min_length=2, max_length=200)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class WorkspaceSettingsIn(BaseModel):
    ai_provider: Literal["default", "auto", "anthropic", "openai", "ollama", "heuristic"] | None = None
    working_language: str | None = Field(default=None, max_length=12)
    portal_enabled: bool | None = None
    portal_title: str | None = Field(default=None, max_length=200)
    brand_color: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    priority_weights: dict[str, float] | None = None

    @field_validator("priority_weights")
    @classmethod
    def _weights(cls, v: dict[str, float] | None) -> dict[str, float] | None:
        if v is None:
            return v
        allowed = {"demand", "revenue", "pain", "momentum", "reach", "rice"}
        if set(v) - allowed:
            raise ValueError(f"Unknown weight(s): {sorted(set(v) - allowed)}")
        if any(w < 0 or w > 1 for w in v.values()):
            raise ValueError("Weights must be between 0 and 1")
        return v


class WorkspaceUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    settings: WorkspaceSettingsIn | None = None


class MemberIn(BaseModel):
    email: EmailStr
    role: Literal["admin", "member"] = "member"


class CustomerFields(BaseModel):
    email: EmailStr | None = None
    name: str | None = Field(default=None, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    country: str | None = Field(default=None, max_length=80)
    plan: str | None = Field(default=None, max_length=80)
    mrr: float | None = Field(default=None, ge=0)
    external_id: str | None = Field(default=None, max_length=120)


class FeedbackIn(BaseModel):
    text: str = Field(min_length=1, max_length=10_000)
    rating: int | None = Field(default=None, ge=1, le=5)
    country: str | None = Field(default=None, max_length=80)
    source: Literal["manual", "api", "email", "import", "widget", "portal"] = "manual"
    created_at: datetime | None = None
    customer: CustomerFields | None = None


class FeedbackPatch(BaseModel):
    status: Literal["new", "reviewed", "archived"] | None = None
    theme_id: int | None = None
    clear_theme: bool = False
    category: str | None = None


class CustomerPatch(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    company: str | None = Field(default=None, max_length=200)
    country: str | None = Field(default=None, max_length=80)
    plan: str | None = Field(default=None, max_length=80)
    mrr: float | None = Field(default=None, ge=0)


class ThemePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)


class MergeIn(BaseModel):
    into_id: int


OppStatus = Literal["under_review", "planned", "in_progress", "shipped", "declined"]


class OpportunityIn(BaseModel):
    title: str = Field(min_length=2, max_length=300)
    description: str = Field(default="", max_length=5000)
    theme_id: int | None = None
    feedback_ids: list[int] = Field(default_factory=list, max_length=500)
    is_public: bool = False


class OpportunityPatch(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=300)
    description: str | None = Field(default=None, max_length=5000)
    status: OppStatus | None = None
    theme_id: int | None = None
    clear_theme: bool = False
    is_public: bool | None = None
    reach: float | None = Field(default=None, ge=0)
    impact: float | None = Field(default=None, ge=0, le=3)
    confidence: float | None = Field(default=None, ge=0, le=1)
    effort: float | None = Field(default=None, gt=0)


class LinkFeedbackIn(BaseModel):
    feedback_ids: list[int] = Field(min_length=1, max_length=500)


class DecisionIn(BaseModel):
    outcome: Literal["build", "defer", "investigate", "decline"]
    rationale: str = Field(min_length=3, max_length=5000)
    update_status: bool = True


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=500)


class ChangelogIn(BaseModel):
    title: str = Field(min_length=2, max_length=300)
    body: str = Field(default="", max_length=20_000)
    published: bool = False


class ChangelogPatch(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=300)
    body: str | None = Field(default=None, max_length=20_000)
    published: bool | None = None


class NotificationPatch(BaseModel):
    subject: str | None = Field(default=None, min_length=1, max_length=300)
    body: str | None = Field(default=None, min_length=1, max_length=20_000)


class SendIn(BaseModel):
    notification_ids: list[int] | None = None
    opportunity_id: int | None = None


class PublicFeedbackIn(BaseModel):
    text: str = Field(min_length=3, max_length=5000)
    email: EmailStr | None = None
    name: str | None = Field(default=None, max_length=200)
    rating: int | None = Field(default=None, ge=1, le=5)
    page_url: str | None = Field(default=None, max_length=1000)
    website: str | None = Field(default=None, max_length=200)  # honeypot: humans never fill this
    meta: dict[str, Any] | None = None


class VoteIn(BaseModel):
    email: EmailStr
    name: str | None = Field(default=None, max_length=200)


class ApiFeedbackIn(CustomerFields):
    text: str = Field(min_length=1, max_length=10_000)
    rating: int | None = Field(default=None, ge=1, le=5)
    source: Literal["api", "email", "import"] = "api"
    created_at: datetime | None = None


class InboundEmailIn(BaseModel):
    from_email: EmailStr = Field(alias="from")
    from_name: str | None = None
    subject: str = ""
    text: str = Field(min_length=1, max_length=20_000)


# ---------------------------------------------------------------- serializers


def iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).isoformat()


def customer_out(c: Customer | None) -> dict[str, Any] | None:
    if c is None:
        return None
    return {"id": c.id, "email": c.email, "name": c.name, "company": c.company, "country": c.country,
            "plan": c.plan, "mrr": c.mrr, "language": c.language}


def theme_brief(t: Theme | None) -> dict[str, Any] | None:
    return None if t is None else {"id": t.id, "name": t.name}


def feedback_out(f: Feedback) -> dict[str, Any]:
    return {
        "id": f.id, "text": f.text, "source": f.source, "rating": f.rating, "country": f.country,
        "page_url": f.page_url, "status": f.status, "created_at": iso(f.created_at),
        "analysis_status": f.analysis_status, "analyzed_by": f.analyzed_by, "analysis_error": f.analysis_error,
        "language": f.language, "translated_text": f.translated_text, "summary": f.summary,
        "sentiment": f.sentiment, "sentiment_label": f.sentiment_label, "category": f.category,
        "urgency": f.urgency, "churn_risk": f.churn_risk, "keywords": f.keywords or [],
        "theme": theme_brief(f.theme), "theme_locked": f.theme_locked, "duplicate_of_id": f.duplicate_of_id,
        "customer": customer_out(f.customer),
    }


def decision_out(d: Decision, opp_title: str | None = None, user_name: str | None = None) -> dict[str, Any]:
    return {"id": d.id, "opportunity_id": d.opportunity_id, "opportunity_title": opp_title, "outcome": d.outcome,
            "rationale": d.rationale, "decided_by": user_name, "evidence_snapshot": d.evidence_snapshot,
            "created_at": iso(d.created_at)}


def changelog_out(e: ChangelogEntry) -> dict[str, Any]:
    return {"id": e.id, "opportunity_id": e.opportunity_id, "title": e.title, "body": e.body,
            "published": e.published, "published_at": iso(e.published_at), "written_by": e.written_by,
            "created_at": iso(e.created_at)}


def notification_out(n: Notification) -> dict[str, Any]:
    return {"id": n.id, "opportunity_id": n.opportunity_id, "customer_id": n.customer_id, "email": n.email,
            "language": n.language, "subject": n.subject, "body": n.body, "status": n.status,
            "channel": n.channel, "error": n.error, "localized_by": n.localized_by,
            "created_at": iso(n.created_at), "sent_at": iso(n.sent_at)}
