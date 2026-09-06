"""Vault retrieve callable — same function HTTP retrieve and Study-logic mount use."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from fastapi import FastAPI

from app.schemas import RetrieveChunk
from app.services.retrieve import retrieve as retrieve_rows

# Study-logic (PR #6) accepts Sequence[Chunk | Mapping] with these keys.
RetrieveFn = Callable[[str, str, int], Sequence[Mapping[str, Any]]]


def bind_retrieve(app: FastAPI) -> RetrieveFn:
    """`retrieve(notebook_id, query, top_k=8) -> list[{id, source_id, text, locator, score, source_filename}]`."""

    def retrieve(notebook_id: str, query: str, top_k: int = 8) -> list[dict[str, Any]]:
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
                RetrieveChunk(
                    id=hit.chunk.id,
                    source_id=hit.chunk.source_id,
                    text=hit.chunk.text,
                    locator=hit.chunk.locator,
                    score=hit.score,
                    source_filename=hit.source_filename,
                ).model_dump()
                for hit in hits
            ]
        finally:
            db.close()

    return retrieve


def try_install_study_logic(app: FastAPI) -> None:
    """Mount Study-logic when `study_logic` is importable (PR #6). Vault smoke does not depend on this.

    TODO(study-logic): PR #6 is not merged. When `packages/study_logic` is on PYTHONPATH:

        from study_logic.api import install_study_logic
        install_study_logic(app, retrieve=app.state.retrieve, prefix="/api/v1")

    Until then this is a no-op stub hook (`app.state.study_logic_mounted is False`).
    """
    try:
        from study_logic.api import install_study_logic  # type: ignore
    except ImportError:
        app.state.study_logic_mounted = False
        return
    install_study_logic(app, retrieve=app.state.retrieve, prefix="/api/v1")
    app.state.study_logic_mounted = True
