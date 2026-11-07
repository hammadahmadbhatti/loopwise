"""Analysis pipeline and the background worker that runs it.

New feedback is stored as ``pending`` and answered immediately; the worker then
analyzes it (language, translation, sentiment, category, urgency, churn signal),
embeds it, flags duplicates and refreshes the workspace's themes. Work is claimed
through the database, so a restart never loses feedback.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from ..ai.embeddings import get_embedder
from ..ai.registry import AIService
from ..config import get_settings
from ..deps import workspace_settings
from ..models import Feedback, Workspace
from .themes import discover_themes, ensure_embeddings, mark_duplicates

log = logging.getLogger("loopwise.analysis")
MAX_ATTEMPTS = 3


def analyze_feedback(db: Session, fb: Feedback, ai: AIService, working_language: str) -> None:
    customer = fb.customer
    context = {
        "rating": fb.rating,  # 1..5 stars when the channel collects one
        "country": fb.country,
        "channel": fb.source,
        "customer_plan": customer.plan if customer else None,
    }
    result, produced_by, error = ai.run("analyze_feedback", fb.text, working_language=working_language, context=context)
    fb.language = result.language
    fb.translated_text = result.translation.strip()
    fb.summary = result.summary.strip()
    fb.sentiment = result.sentiment
    fb.sentiment_label = result.sentiment_label
    fb.category = result.category
    fb.urgency = result.urgency
    fb.churn_risk = result.churn_risk
    fb.keywords = result.keywords
    fb.analyzed_by = produced_by
    fb.analysis_error = error
    fb.analysis_status = "done"
    fb.analyzed_at = datetime.now(timezone.utc)
    fb.embedding = None  # text may have changed (translation), re-embed
    if customer is not None and result.language not in ("", "und"):
        customer.language = result.language


def process_pending(db: Session, limit: int | None = None, workspace_id: int | None = None) -> int:
    """Analyze up to ``limit`` pending items. Returns how many were processed."""
    limit = limit or get_settings().worker_batch_size
    q = select(Feedback.id).where(Feedback.analysis_status == "pending").order_by(Feedback.id).limit(limit)
    if workspace_id is not None:
        q = q.where(Feedback.workspace_id == workspace_id)
    ids = list(db.scalars(q))
    if not ids:
        return 0
    # claim the rows (status guard makes concurrent workers skip each other's work)
    db.execute(update(Feedback).where(Feedback.id.in_(ids), Feedback.analysis_status == "pending")
               .values(analysis_status="processing"))
    db.commit()

    items = list(db.scalars(select(Feedback).where(Feedback.id.in_(ids), Feedback.analysis_status == "processing")))
    by_ws: dict[int, list[Feedback]] = defaultdict(list)
    for fb in items:
        by_ws[fb.workspace_id].append(fb)

    embedder = get_embedder()
    for ws_id, ws_items in by_ws.items():
        ws = db.get(Workspace, ws_id)
        settings = workspace_settings(ws)
        ai = AIService(settings.get("ai_provider"))
        done: list[Feedback] = []
        for fb in ws_items:
            fb.analysis_attempts += 1
            try:
                analyze_feedback(db, fb, ai, settings.get("working_language", "en"))
                done.append(fb)
            except Exception as exc:  # noqa: BLE001 - never let one item kill the batch
                log.exception("analysis failed for feedback %s", fb.id)
                fb.analysis_error = str(exc)[:500]
                fb.analysis_status = "pending" if fb.analysis_attempts < MAX_ATTEMPTS else "failed"
        db.flush()
        try:
            ensure_embeddings(db, done, embedder)
            mark_duplicates(db, ws_id, done, embedder)
            if done:
                discover_themes(db, ws, ai)
        except Exception:  # noqa: BLE001 - analysis results are still worth saving
            log.exception("theme refresh failed for workspace %s", ws_id)
        db.commit()
    return len(items)


def drain(db: Session, workspace_id: int | None = None) -> int:
    """Process everything pending (used by tests and after large imports in sync mode)."""
    total = 0
    while True:
        n = process_pending(db, workspace_id=workspace_id)
        if n == 0:
            return total
        total += n


def recover_stuck(db: Session) -> None:
    """Rows left 'processing' by a crash go back to the queue on startup."""
    db.execute(update(Feedback).where(Feedback.analysis_status == "processing").values(analysis_status="pending"))
    db.commit()


class AnalysisWorker:
    def __init__(self, session_factory: sessionmaker, interval: float):
        self._factory = session_factory
        self._interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        with self._factory() as db:
            recover_stuck(db)
        self._thread = threading.Thread(target=self._run, name="analysis-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)

    def _run(self) -> None:
        log.info("analysis worker started")
        while not self._stop.is_set():
            processed = 0
            try:
                with self._factory() as db:
                    processed = process_pending(db)
            except Exception:  # noqa: BLE001
                log.exception("worker iteration failed")
            if processed == 0:
                self._stop.wait(self._interval)
            else:
                time.sleep(0.05)
