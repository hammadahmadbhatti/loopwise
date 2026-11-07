"""FastAPI dependencies: authentication, tenant scoping and role checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Depends, Header, HTTPException, Path, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import Membership, User, Workspace
from .security import decode_access_token, hash_api_key

bearer = HTTPBearer(auto_error=False)

DEFAULT_PRIORITY_WEIGHTS = {
    "demand": 0.30,
    "revenue": 0.25,
    "pain": 0.20,
    "momentum": 0.10,
    "reach": 0.05,
    "rice": 0.10,
}

DEFAULT_WORKSPACE_SETTINGS: dict[str, Any] = {
    "ai_provider": "default",  # "default" = server setting; or anthropic|openai|ollama|heuristic
    "working_language": "en",
    "portal_enabled": True,
    "portal_title": "",
    "brand_color": "#4f46e5",
    "priority_weights": DEFAULT_PRIORITY_WEIGHTS,
}


def workspace_settings(ws: Workspace) -> dict[str, Any]:
    merged = {**DEFAULT_WORKSPACE_SETTINGS, **(ws.settings or {})}
    merged["priority_weights"] = {**DEFAULT_PRIORITY_WEIGHTS, **(merged.get("priority_weights") or {})}
    return merged


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    user_id = decode_access_token(creds.credentials)
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    return user


@dataclass
class WorkspaceContext:
    workspace: Workspace
    user: User
    role: str

    @property
    def id(self) -> int:
        return self.workspace.id

    @property
    def is_admin(self) -> bool:
        return self.role in ("owner", "admin")


def get_workspace_ctx(
    wid: int = Path(..., description="Workspace id"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceContext:
    membership = db.scalar(select(Membership).where(Membership.workspace_id == wid, Membership.user_id == user.id))
    if membership is None:
        # 404 rather than 403 so workspace ids can't be probed
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    return WorkspaceContext(workspace=membership.workspace, user=user, role=membership.role)


def require_admin(ctx: WorkspaceContext = Depends(get_workspace_ctx)) -> WorkspaceContext:
    if not ctx.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return ctx


def get_workspace_by_api_key(x_api_key: str | None = Header(default=None), db: Session = Depends(get_db)) -> Workspace:
    if not x_api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing X-API-Key header")
    ws = db.scalar(select(Workspace).where(Workspace.api_key_hash == hash_api_key(x_api_key)))
    if ws is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")
    return ws
