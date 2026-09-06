from __future__ import annotations

from functools import wraps
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse

from study_logic.engine import StudyEngine
from study_logic.errors import StudyError
from study_logic.models import AttemptBody, ConfirmBody
from study_logic.vault import RetrieveFn, create_fixture_vault


def _guard(fn):
    @wraps(fn)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except StudyError as exc:
            return JSONResponse(status_code=exc.status, content=exc.to_json())

    return wrapped


def create_router(retrieve: RetrieveFn | None = None, engine: StudyEngine | None = None) -> APIRouter:
    """S0 routes without `/api/v1`. Backend mounts with prefix=\"/api/v1\"."""
    study = engine or StudyEngine(retrieve=retrieve)
    api = APIRouter()

    @api.post("/notebooks/{notebook_id}/topics/propose")
    @_guard
    def propose(notebook_id: str) -> list[dict[str, Any]]:
        return [t.as_dict() for t in study.propose_topics(notebook_id)]

    @api.post("/notebooks/{notebook_id}/topics/confirm")
    @_guard
    def confirm(notebook_id: str, body: ConfirmBody | None = None) -> list[dict[str, Any]]:
        payload = body or ConfirmBody()
        return [
            t.as_dict()
            for t in study.confirm_topics(
                notebook_id,
                names=payload.names,
                topics=payload.topics,
                topic_ids=payload.topic_ids,
            )
        ]

    @api.get("/notebooks/{notebook_id}/topics")
    @_guard
    def list_topics(notebook_id: str) -> list[dict[str, Any]]:
        return [t.as_dict() for t in study.list_topics(notebook_id)]

    @api.post("/notebooks/{notebook_id}/quizzes")
    @_guard
    def create_quiz(notebook_id: str) -> dict[str, Any]:
        return study.create_quiz(notebook_id)

    @api.post("/quizzes/{quiz_id}/attempts")
    @_guard
    def grade(quiz_id: str, body: AttemptBody) -> dict[str, Any]:
        return study.grade_attempt(quiz_id, body.item_id, body.selected_choice_id)

    @api.get("/notebooks/{notebook_id}/scoreboard")
    @_guard
    def scoreboard(notebook_id: str) -> dict[str, Any]:
        return study.scoreboard(notebook_id).as_dict()

    return api


def study_error_handler(_request: Request, exc: StudyError) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content=exc.to_json())


def install_study_logic(
    app: FastAPI,
    *,
    retrieve: RetrieveFn | None = None,
    engine: StudyEngine | None = None,
    prefix: str = "/api/v1",
) -> APIRouter:
    """DEMO mount: one FastAPI process on :8000 includes this router."""
    mounted = create_router(retrieve=retrieve, engine=engine)
    app.add_exception_handler(StudyError, study_error_handler)
    app.include_router(mounted, prefix=prefix)
    return mounted


# Fixture-backed default for `from study_logic.api import router`.
# Production DEMO should call create_router(retrieve=backend_retrieve) instead.
router = create_router(retrieve=create_fixture_vault().retrieve)
