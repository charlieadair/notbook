from fastapi import Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import get_db
from app.inference.base import InferenceAdapter
from app.models import Chunk, Notebook


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_inference(request: Request) -> InferenceAdapter:
    return request.app.state.inference


def get_notebook(
    notebook_id: str,
    db: Session = Depends(get_db),
) -> Notebook:
    notebook = db.get(Notebook, notebook_id)
    if notebook is None:
        raise HTTPException(status_code=404, detail="Notebook not found")
    return notebook


def chunk_count_for(db: Session, source_id: str) -> int:
    return int(
        db.scalar(select(func.count()).select_from(Chunk).where(Chunk.source_id == source_id))
        or 0
    )
