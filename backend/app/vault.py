"""Vault retrieve / sample-chunks callables — same functions HTTP and Study-logic mount use."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import timezone
from typing import Any, TypedDict

from fastapi import FastAPI
from sqlalchemy import select
from study_logic.api import install_study_logic

from app.models import Chunk as DbChunk
from app.models import Source
from app.services.retrieve import retrieve as retrieve_rows


class Chunk(TypedDict):
    """install_study_logic retrieve / list_chunks contract — keep these keys exact."""

    id: str
    source_id: str
    text: str
    locator: dict[str, Any]
    score: float
    source_filename: str


RetrieveFn = Callable[[str, str, int], Sequence[Chunk]]
ListChunksFn = Callable[[str, int], Sequence[Chunk]]


def bind_retrieve(app: FastAPI) -> RetrieveFn:
    def retrieve(notebook_id: str, query: str, top_k: int = 8) -> list[Chunk]:
        if not (query or "").strip():
            return []
        db = app.state.SessionLocal()
        try:
            hits = retrieve_rows(
                db,
                inference=app.state.inference,
                notebook_id=notebook_id,
                query=query,
                top_k=top_k,
            )
            return [
                Chunk(
                    id=hit.chunk.id,
                    source_id=hit.chunk.source_id,
                    text=hit.chunk.text,
                    locator=hit.chunk.locator,
                    score=float(hit.score),
                    source_filename=hit.source_filename or "",
                )
                for hit in hits
            ]
        finally:
            db.close()

    return retrieve


def _created_ts(source: Source) -> float:
    dt = source.created_at
    if dt is None:
        return 0.0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def bind_list_chunks(app: FastAPI) -> ListChunksFn:
    """In-process GET /notebooks/{id}/chunks — propose must not retrieve(query='')."""

    def list_chunks(notebook_id: str, limit: int = 32) -> list[Chunk]:
        db = app.state.SessionLocal()
        try:
            sources = {
                row.id: row
                for row in db.scalars(select(Source).where(Source.notebook_id == notebook_id)).all()
            }
            rows = list(db.scalars(select(DbChunk).where(DbChunk.notebook_id == notebook_id)).all())
            rows.sort(
                key=lambda chunk: (
                    -(_created_ts(sources[chunk.source_id]) if chunk.source_id in sources else 0.0),
                    (chunk.locator or {}).get("order") or 0,
                )
            )
            return [
                Chunk(
                    id=row.id,
                    source_id=row.source_id,
                    text=row.text,
                    locator=row.locator,
                    score=0.0,
                    source_filename=sources[row.source_id].filename if row.source_id in sources else "",
                )
                for row in rows[:limit]
            ]
        finally:
            db.close()

    return list_chunks


def mount_study_logic(app: FastAPI) -> None:
    """Include Study-logic on the same :8000 app with retrieve + sample-chunks callables."""
    inference = getattr(app.state, "inference", None)
    complete = getattr(inference, "complete", None) if inference is not None else None
    install_study_logic(
        app,
        retrieve=app.state.retrieve,
        list_chunks=app.state.list_chunks,
        complete=complete,
        prefix="/api/v1",
    )
    app.state.study_logic_mounted = True
