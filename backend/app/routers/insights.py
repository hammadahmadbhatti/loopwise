"""Dashboard overview and Ask-your-feedback."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import WorkspaceContext, get_workspace_ctx
from ..schemas import AskIn
from ..services import insights

router = APIRouter(prefix="/api/workspaces/{wid}/insights", tags=["insights"])


@router.get("/overview")
def overview(ctx: WorkspaceContext = Depends(get_workspace_ctx), db: Session = Depends(get_db),
             days: int = Query(30, ge=7, le=365)):
    return insights.overview(db, ctx.workspace, days)


@router.post("/ask")
def ask(body: AskIn, ctx: WorkspaceContext = Depends(get_workspace_ctx), db: Session = Depends(get_db)):
    return insights.ask(db, ctx.workspace, body.question.strip())
