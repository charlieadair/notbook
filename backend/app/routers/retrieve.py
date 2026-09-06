from fastapi import APIRouter, Depends, Request

from app.deps import get_notebook
from app.models import Notebook
from app.schemas import RetrieveIn, RetrieveOut

router = APIRouter(prefix="/api/v1", tags=["retrieve"])


@router.post("/notebooks/{notebook_id}/retrieve", response_model=RetrieveOut)
def retrieve_chunks(
    body: RetrieveIn,
    request: Request,
    notebook: Notebook = Depends(get_notebook),
) -> RetrieveOut:
    retrieve = request.app.state.retrieve
    return RetrieveOut(chunks=retrieve(notebook.id, body.query, body.top_k))
