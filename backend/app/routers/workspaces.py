"""Workspace settings, team members, API keys and AI provider status."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.embeddings import get_embedder
from ..ai.registry import AIService, provider_status
from ..config import get_settings
from ..db import get_db
from ..deps import WorkspaceContext, get_current_user, get_workspace_ctx, require_admin, workspace_settings
from ..models import Membership, User
from ..schemas import MemberIn, WorkspaceUpdateIn
from ..security import hash_api_key, new_api_key
from .auth import create_workspace

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


def workspace_out(ctx: WorkspaceContext) -> dict:
    ws = ctx.workspace
    app_url = get_settings().public_app_url.rstrip("/")
    return {
        "id": ws.id, "name": ws.name, "slug": ws.slug, "role": ctx.role, "public_key": ws.public_key,
        "api_key_prefix": ws.api_key_prefix, "settings": workspace_settings(ws),
        "portal_url": f"{app_url}/p/{ws.slug}",
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create(body: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    name = str(body.get("name", "")).strip()
    if len(name) < 2:
        raise HTTPException(422, "Workspace name must be at least 2 characters")
    ws = create_workspace(db, user, name)
    db.commit()
    return {"id": ws.id, "name": ws.name, "slug": ws.slug, "role": "owner"}


@router.get("/{wid}")
def get_workspace(ctx: WorkspaceContext = Depends(get_workspace_ctx)):
    return workspace_out(ctx)


@router.patch("/{wid}")
def update_workspace(body: WorkspaceUpdateIn, ctx: WorkspaceContext = Depends(require_admin), db: Session = Depends(get_db)):
    ws = ctx.workspace
    if body.name:
        ws.name = body.name.strip()
    if body.settings:
        current = workspace_settings(ws)
        patch = body.settings.model_dump(exclude_none=True)
        if "priority_weights" in patch:
            patch["priority_weights"] = {**current["priority_weights"], **patch["priority_weights"]}
        ws.settings = {**current, **patch}
    db.commit()
    return workspace_out(ctx)


@router.post("/{wid}/api-key")
def rotate_api_key(ctx: WorkspaceContext = Depends(require_admin), db: Session = Depends(get_db)):
    key = new_api_key()
    ctx.workspace.api_key_hash = hash_api_key(key)
    ctx.workspace.api_key_prefix = key[:10]
    db.commit()
    return {"api_key": key, "note": "Store this key now; it is only shown once."}


@router.get("/{wid}/members")
def list_members(ctx: WorkspaceContext = Depends(get_workspace_ctx), db: Session = Depends(get_db)):
    rows = db.execute(
        select(User, Membership.role).join(Membership, Membership.user_id == User.id)
        .where(Membership.workspace_id == ctx.id).order_by(User.id)
    ).all()
    return [{"id": u.id, "email": u.email, "name": u.name, "role": r} for u, r in rows]


@router.post("/{wid}/members", status_code=status.HTTP_201_CREATED)
def add_member(body: MemberIn, ctx: WorkspaceContext = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None:
        raise HTTPException(404, "No account with that email yet. Ask them to sign up first.")
    if db.scalar(select(Membership).where(Membership.workspace_id == ctx.id, Membership.user_id == user.id)):
        raise HTTPException(409, "Already a member")
    db.add(Membership(workspace_id=ctx.id, user_id=user.id, role=body.role))
    db.commit()
    return {"id": user.id, "email": user.email, "name": user.name, "role": body.role}


@router.get("/{wid}/ai")
def ai_status(ctx: WorkspaceContext = Depends(get_workspace_ctx)):
    pref = workspace_settings(ctx.workspace).get("ai_provider")
    service = AIService(pref)
    embedder = get_embedder()
    return {
        "preference": pref,
        "server_default": get_settings().ai_provider,
        "active": {"name": service.primary.name, "model": service.primary.model, "note": service.note},
        "providers": provider_status(),
        "embeddings": {"name": embedder.name, "model": embedder.model},
    }


@router.post("/{wid}/ai/test")
def ai_test(body: dict, ctx: WorkspaceContext = Depends(get_workspace_ctx)):
    text = str(body.get("text") or "").strip()[:2000]
    if not text:
        raise HTTPException(422, "Provide some text to analyze")
    settings = workspace_settings(ctx.workspace)
    service = AIService(settings.get("ai_provider"))
    result, by, error = service.run("analyze_feedback", text, working_language=settings["working_language"], context={})
    return {"result": result.model_dump(), "produced_by": by, "error": error}
