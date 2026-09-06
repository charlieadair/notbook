"""Vault retrieve callable — same function HTTP retrieve and Study-logic mount use."""

from __future__ import annotations

from fastapi import FastAPI

from app.schemas import RetrieveChunk
from app.services.retrieve import retrieve as retrieve_rows


def bind_retrieve(app: FastAPI):
    """Return `retrieve(notebook_id, query, top_k)` with Study-logic field names."""

    def retrieve(notebook_id: str, query: str, top_k: int = 8) -> list[RetrieveChunk]:
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
                )
                for hit in hits
            ]
        finally:
            db.close()

    return retrieve


def try_install_study_logic(app: FastAPI) -> None:
    """Mount Study-logic if the package is importable (PR #6). Vault smoke does not depend on this.

    TODO(study-logic): when `study_logic` is on PYTHONPATH:
        from study_logic.api import install_study_logic
        install_study_logic(app, retrieve=app.state.retrieve, prefix="/api/v1")
    """
    try:
        from study_logic.api import install_study_logic  # type: ignore
    except ImportError:
        app.state.study_logic_mounted = False
        return
    install_study_logic(app, retrieve=app.state.retrieve, prefix="/api/v1")
    app.state.study_logic_mounted = True
