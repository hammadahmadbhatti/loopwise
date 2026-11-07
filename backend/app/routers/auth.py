"""Sign up, sign in and the current user's workspaces."""

from __future__ import annotations

import re
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import DEFAULT_WORKSPACE_SETTINGS, get_current_user
from ..models import Membership, User, Workspace
from ..schemas import LoginIn, RegisterIn
from ..security import create_access_token, hash_password, new_public_key, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def unique_slug(db: Session, name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "workspace"
    slug = base
    while db.scalar(select(Workspace.id).where(Workspace.slug == slug)):
        slug = f"{base}-{secrets.token_hex(2)}"
    return slug


def create_workspace(db: Session, owner: User, name: str) -> Workspace:
    ws = Workspace(name=name.strip(), slug=unique_slug(db, name), public_key=new_public_key(),
                   settings=dict(DEFAULT_WORKSPACE_SETTINGS))
    db.add(ws)
    db.flush()
    db.add(Membership(user_id=owner.id, workspace_id=ws.id, role="owner"))
    return ws


def user_out(db: Session, user: User) -> dict:
    rows = db.execute(
        select(Workspace, Membership.role).join(Membership, Membership.workspace_id == Workspace.id)
        .where(Membership.user_id == user.id).order_by(Workspace.id)
    ).all()
    return {
        "id": user.id, "email": user.email, "name": user.name,
        "workspaces": [{"id": w.id, "name": w.name, "slug": w.slug, "role": role} for w, role in rows],
    }


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")
    user = User(email=email, name=body.name.strip(), password_hash=hash_password(body.password))
    db.add(user)
    db.flush()
    create_workspace(db, user, body.workspace_name)
    db.commit()
    return {"access_token": create_access_token(user.id), "token_type": "bearer", "user": user_out(db, user)}


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")
    return {"access_token": create_access_token(user.id), "token_type": "bearer", "user": user_out(db, user)}


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return user_out(db, user)
