from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.inference.base import InferenceAdapter
from app.models import Chunk, Source
from app.services.embeddings import cosine_similarity, unpack_embedding


@dataclass
class ScoredChunk:
    chunk: Chunk
    score: float
    source_filename: str | None


def _sanitize_fts_query(query: str) -> str:
    terms = re.findall(r"[A-Za-z0-9_]+", query)
    return " OR ".join(terms)


def _keyword_score(query: str, body: str) -> float:
    q_terms = set(re.findall(r"[a-z0-9]+", query.lower()))
    if not q_terms:
        return 0.0
    t_terms = set(re.findall(r"[a-z0-9]+", body.lower()))
    return len(q_terms & t_terms) / len(q_terms)


def _fts_scores(db: Session, notebook_id: str, query: str, limit: int) -> dict[str, float]:
    match = _sanitize_fts_query(query)
    if not match:
        return {}
    try:
        rows = db.execute(
            text(
                """
                SELECT fts.chunk_id AS chunk_id, bm25(chunks_fts) AS rank
                FROM chunks_fts AS fts
                JOIN chunks AS c ON c.id = fts.chunk_id
                WHERE c.notebook_id = :notebook_id
                  AND fts MATCH :match
                ORDER BY rank
                LIMIT :limit
                """
            ),
            {"notebook_id": notebook_id, "match": match, "limit": limit},
        ).all()
    except Exception:
        return {}
    scores: dict[str, float] = {}
    for chunk_id, rank in rows:
        # FTS5 bm25 is typically negative; map to (0, 1].
        scores[str(chunk_id)] = 1.0 / (1.0 + abs(float(rank)))
    return scores


def retrieve(
    db: Session,
    *,
    inference: InferenceAdapter,
    notebook_id: str,
    query: str,
    top_k: int = 8,
) -> list[ScoredChunk]:
    chunks = list(
        db.scalars(select(Chunk).where(Chunk.notebook_id == notebook_id)).all()
    )
    if not chunks:
        return []

    sources = {
        s.id: s.filename
        for s in db.scalars(select(Source).where(Source.notebook_id == notebook_id)).all()
    }

    scores: dict[str, float] = {}

    embedded = [c for c in chunks if c.embedding]
    if embedded:
        try:
            query_vec = inference.embed([query])[0]
        except Exception:
            query_vec = None
        if query_vec is not None:
            for chunk in embedded:
                vec = unpack_embedding(chunk.embedding)
                scores[chunk.id] = cosine_similarity(query_vec, vec)

    # FTS5 / keyword fallback for chunks without embeddings, or if vectors produced nothing.
    need_fallback = (not scores) or any(c.embedding is None for c in chunks)
    if need_fallback:
        fts = _fts_scores(db, notebook_id, query, limit=max(top_k * 4, 16))
        for chunk in chunks:
            existing = scores.get(chunk.id, 0.0)
            if chunk.embedding is None or existing == 0.0:
                fts_score = fts.get(chunk.id)
                if fts_score is None:
                    fts_score = _keyword_score(query, chunk.text)
                if fts_score > existing:
                    scores[chunk.id] = fts_score

    ranked = sorted(
        chunks,
        key=lambda c: scores.get(c.id, 0.0),
        reverse=True,
    )
    out: list[ScoredChunk] = []
    for chunk in ranked:
        score = scores.get(chunk.id, 0.0)
        if score <= 0.0 and len(out) >= top_k:
            continue
        out.append(
            ScoredChunk(
                chunk=chunk,
                score=float(score),
                source_filename=sources.get(chunk.source_id),
            )
        )
        if len(out) >= top_k:
            break
    return out
