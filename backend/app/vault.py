"""Vault retrieve callable — same function HTTP retrieve and Study-logic mount use."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, TypedDict

from fastapi import FastAPI
from study_logic.api import install_study_logic

from app.services.retrieve import retrieve as retrieve_rows


class Chunk(TypedDict):
    """install_study_logic retrieve contract — keep these keys exact."""

    id: str
    source_id: str
    text: str
    locator: dict[str, Any]
    score: float
    source_filename: str


RetrieveFn = Callable[[str, str, int], Sequence[Chunk]]


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


def mount_study_logic(app: FastAPI) -> None:
    """Include Study-logic on the same :8000 app with the vault retrieve callable."""
    install_study_logic(app, retrieve=app.state.retrieve, prefix="/api/v1")
    app.state.study_logic_mounted = True
