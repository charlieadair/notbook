from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_inference, get_notebook
from app.inference.base import InferenceAdapter
from app.models import Notebook
from app.schemas import RetrieveChunk, RetrieveIn, RetrieveOut
from app.services.retrieve import retrieve

router = APIRouter(prefix="/api/v1", tags=["retrieve"])


@router.post("/notebooks/{notebook_id}/retrieve", response_model=RetrieveOut)
def retrieve_chunks(
    body: RetrieveIn,
    notebook: Notebook = Depends(get_notebook),
    db: Session = Depends(get_db),
    inference: InferenceAdapter = Depends(get_inference),
) -> RetrieveOut:
    if not body.query.strip():
        return RetrieveOut(chunks=[])
    hits = retrieve(
        db,
        inference=inference,
        notebook_id=notebook.id,
        query=body.query,
        top_k=body.top_k,
    )
    return RetrieveOut(
        chunks=[
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
    )
