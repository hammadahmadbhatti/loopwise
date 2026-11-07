"""Loopwise API: AI-powered global customer feedback and decision-making platform."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import get_settings
from .db import SessionLocal, run_migrations
from .routers import auth, customers, feedback, insights, loop, opportunities, public, themes, workspaces
from .services.analysis import AnalysisWorker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("loopwise")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.assert_production_safe()
    if settings.secret_is_weak:
        log.warning("SECRET_KEY is weak or the development default; fine locally, refused when ENVIRONMENT=production")
    if settings.auto_migrate:
        run_migrations()
    worker = None
    if settings.worker_enabled:
        worker = AnalysisWorker(SessionLocal, settings.worker_interval_seconds)
        worker.start()
    yield
    if worker:
        worker.stop()


app = FastAPI(
    title="Loopwise API",
    version="1.0.0",
    description="Collect customer feedback from every channel and language, let AI turn it into themes and "
                "prioritized opportunities, decide with evidence, and close the loop with customers.",
    lifespan=lifespan,
)

# Dashboard API: only the configured app origins. Public widget/portal/ingest: any origin (they carry no cookies).
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=None,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def public_cors(request: Request, call_next):
    is_public = request.url.path.startswith("/api/public/")
    if is_public and request.method == "OPTIONS":
        return JSONResponse({}, headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Max-Age": "86400",
        })
    response = await call_next(request)
    if is_public:
        response.headers["Access-Control-Allow-Origin"] = "*"
    return response


for r in (auth, workspaces, feedback, customers, themes, opportunities, insights, loop, public):
    app.include_router(r.router)


@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok"}
