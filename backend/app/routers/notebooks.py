import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_notebook
from app.models import Notebook
from app.schemas import NotebookCreate, NotebookOut

router = APIRouter(prefix="/api/v1", tags=["notebooks"])


@router.post("/notebooks", response_model=NotebookOut, status_code=status.HTTP_201_CREATED)
def create_notebook(body: NotebookCreate, db: Session = Depends(get_db)) -> Notebook:
    notebook = Notebook(
        id=str(uuid.uuid4()),
        title=body.title.strip(),
        created_at=datetime.now(timezone.utc),
    )
    if not notebook.title:
        raise HTTPException(status_code=422, detail="title must not be empty")
    db.add(notebook)
    db.flush()
    return notebook


@router.get("/notebooks", response_model=list[NotebookOut])
def list_notebooks(db: Session = Depends(get_db)) -> list[Notebook]:
    return list(db.scalars(select(Notebook).order_by(Notebook.created_at.desc())).all())


@router.get("/notebooks/{notebook_id}", response_model=NotebookOut)
def get_notebook_route(notebook: Notebook = Depends(get_notebook)) -> Notebook:
    return notebook
