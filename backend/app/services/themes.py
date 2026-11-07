"""Theme discovery: groups feedback that talks about the same thing.

Pipeline: embed working-language text -> cosine distance matrix -> average-linkage
agglomerative clustering with a distance threshold (no need to guess k) -> match
new clusters to existing themes by member overlap so theme ids (and the
opportunities linked to them) stay stable across re-runs -> name new themes with
the workspace's AI provider.
"""

from __future__ import annotations

import logging
import math
from collections import Counter, defaultdict

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai.embeddings import Embedder, cosine, get_embedder
from ..ai.heuristic import NEGATIVE, POSITIVE
from ..ai.registry import AIService
from ..ai.textutil import clean_token, is_content, tokenize
from ..deps import workspace_settings
from ..models import Feedback, Opportunity, Theme, Workspace

log = logging.getLogger("loopwise.themes")

MAX_CLUSTER_ITEMS = 3000
MIN_THEME_SIZE = 2
REUSE_OVERLAP = 0.3
_SENTIMENT = set(POSITIVE) | set(NEGATIVE)


def ensure_embeddings(db: Session, items: list[Feedback], embedder: Embedder) -> None:
    stale = [f for f in items if f.embedding is None or f.embedding_model != embedder.label]
    for i in range(0, len(stale), 64):
        chunk = stale[i:i + 64]
        vectors = embedder.embed([f.working_text for f in chunk])
        for fb, vec in zip(chunk, vectors):
            fb.embedding = vec
            fb.embedding_model = embedder.label
    if stale:
        db.flush()


def mark_duplicates(db: Session, ws_id: int, new_items: list[Feedback], embedder: Embedder) -> int:
    """Flag near-identical feedback (same complaint submitted twice, copy-paste spam)."""
    if not new_items:
        return 0
    recent = list(
        db.scalars(
            select(Feedback)
            .where(Feedback.workspace_id == ws_id, Feedback.analysis_status == "done",
                   Feedback.embedding_model == embedder.label, Feedback.duplicate_of_id.is_(None))
            .order_by(Feedback.id.desc())
            .limit(1000)
        )
    )
    pool = {f.id: f for f in recent}
    for f in new_items:
        pool.setdefault(f.id, f)
    ordered = sorted(pool.values(), key=lambda f: f.id)
    if len(ordered) < 2:
        return 0
    X = embedder.matrix([f.embedding for f in ordered])
    index = {f.id: i for i, f in enumerate(ordered)}
    marked = 0
    for f in new_items:
        i = index[f.id]
        sims = cosine(X[i], X).ravel()
        for j in np.argsort(-sims):
            other = ordered[int(j)]
            if other.id >= f.id:
                continue
            if sims[j] >= embedder.dup_threshold:
                f.duplicate_of_id = other.duplicate_of_id or other.id
                marked += 1
            break
    return marked


def theme_keywords(docs: list[str], corpus_df: Counter, corpus_size: int, limit: int = 5) -> list[str]:
    df: Counter = Counter()
    for d in docs:
        seq = [c if is_content(c) and c not in _SENTIMENT else None for c in (clean_token(t) for t in tokenize(d))]
        terms = {t for t in seq if t} | {f"{a} {b}" for a, b in zip(seq, seq[1:]) if a and b}
        df.update(terms)
    scored = []
    for term, n in df.items():
        if n < 2 and len(docs) > 2:
            continue
        idf = math.log((1 + corpus_size) / (1 + corpus_df.get(term, n))) + 1
        bonus = 1.3 if " " in term else 1.0
        scored.append((n / len(docs) * idf * bonus, term))
    out: list[str] = []
    for _, term in sorted(scored, reverse=True):
        if any(term in o or o in term for o in out):
            continue
        out.append(term)
        if len(out) >= limit:
            break
    return out


def _corpus_df(docs: list[str]) -> Counter:
    df: Counter = Counter()
    for d in docs:
        seq = [c if is_content(c) else None for c in (clean_token(t) for t in tokenize(d))]
        df.update({t for t in seq if t} | {f"{a} {b}" for a, b in zip(seq, seq[1:]) if a and b})
    return df


def discover_themes(db: Session, ws: Workspace, ai: AIService | None = None) -> dict:
    embedder = get_embedder()
    items = list(
        db.scalars(
            select(Feedback)
            .where(Feedback.workspace_id == ws.id, Feedback.analysis_status == "done",
                   Feedback.duplicate_of_id.is_(None), Feedback.status != "archived")
            .order_by(Feedback.created_at.desc())
            .limit(MAX_CLUSTER_ITEMS)
        )
    )
    ensure_embeddings(db, items, embedder)
    movable = [f for f in items if not f.theme_locked]
    summary = {"items": len(items), "themes_created": 0, "themes_reused": 0, "themes_archived": 0, "embedder": embedder.label}
    if len(movable) < MIN_THEME_SIZE:
        return summary

    X = embedder.matrix([f.embedding for f in movable])
    dist = np.clip(1.0 - cosine(X, X), 0.0, 2.0).astype(np.float64)
    np.fill_diagonal(dist, 0.0)
    labels = AgglomerativeClustering(
        n_clusters=None, metric="precomputed", linkage="average", distance_threshold=embedder.cluster_distance
    ).fit_predict(dist)

    clusters: dict[int, list[int]] = defaultdict(list)
    for idx, lab in enumerate(labels):
        clusters[int(lab)].append(idx)

    previous: dict[int, set[int]] = defaultdict(set)
    for f in movable:
        if f.theme_id:
            previous[f.theme_id].add(f.id)
    themes_by_id = {t.id: t for t in db.scalars(select(Theme).where(Theme.workspace_id == ws.id))}

    corpus_texts = [f.working_text for f in items]
    corpus_df = _corpus_df(corpus_texts)
    used: set[int] = set()
    to_label: list[tuple[Theme, list[Feedback]]] = []
    assignment: dict[int, int | None] = {f.id: None for f in movable}

    for members in sorted(clusters.values(), key=len, reverse=True):
        if len(members) < MIN_THEME_SIZE:
            continue
        member_items = [movable[i] for i in members]
        ids = {f.id for f in member_items}
        best_id, best_overlap = None, 0.0
        for tid, old in previous.items():
            if tid in used or tid not in themes_by_id:
                continue
            overlap = len(ids & old) / len(ids | old)
            if overlap > best_overlap:
                best_id, best_overlap = tid, overlap
        docs = [f.working_text for f in member_items]
        keywords = theme_keywords(docs, corpus_df, len(corpus_texts))
        if best_id is not None and best_overlap >= REUSE_OVERLAP:
            theme = themes_by_id[best_id]
            theme.archived = False
            summary["themes_reused"] += 1
        else:
            theme = Theme(workspace_id=ws.id, name="New theme", keywords=keywords)
            db.add(theme)
            db.flush()
            themes_by_id[theme.id] = theme
            summary["themes_created"] += 1
            # label using the items closest to the cluster centre
            centre = np.asarray(X[members].mean(axis=0)).ravel()
            sims = cosine(X[members], centre.reshape(1, -1)).ravel()
            ranked = [member_items[int(i)] for i in np.argsort(-sims)]
            to_label.append((theme, ranked))
        theme.keywords = keywords
        used.add(theme.id)
        for f in member_items:
            assignment[f.id] = theme.id

    for f in movable:
        f.theme_id = assignment[f.id]

    # Archive themes that lost all members (keep ones with locked feedback or linked opportunities)
    db.flush()
    live = {tid for tid in db.scalars(select(Feedback.theme_id).where(Feedback.workspace_id == ws.id,
                                                                      Feedback.theme_id.is_not(None)).distinct())}
    linked = set(db.scalars(select(Opportunity.theme_id).where(Opportunity.workspace_id == ws.id,
                                                               Opportunity.theme_id.is_not(None))))
    for tid, theme in themes_by_id.items():
        if tid not in live and not theme.archived and tid not in linked:
            theme.archived = True
            summary["themes_archived"] += 1

    if to_label:
        ai = ai or AIService(workspace_settings(ws).get("ai_provider"))
        for theme, ranked in to_label:
            label, by, _ = ai.run("label_theme", [f.working_text for f in ranked[:12]], keywords=theme.keywords)
            if not theme.name_locked:
                theme.name = label.name
                theme.description = label.description
                theme.labeled_by = by
    db.flush()
    log.info("themes for workspace %s: %s", ws.id, summary)
    return summary
