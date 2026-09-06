from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import get_db
from app.deps import chunk_count_for, get_inference, get_notebook, get_settings
from app.inference.base import InferenceAdapter
from app.models import Notebook
from app.schemas import PasteIn, SourceOut
from app.services.ingest import ingest_paste, ingest_upload

router = APIRouter(prefix="/api/v1", tags=["ingest"])


def _source_out(db: Session, source) -> SourceOut:
    return SourceOut.model_validate(source).model_copy(
        update={"chunk_count": chunk_count_for(db, source.id)}
    )


@router.post(
    "/notebooks/{notebook_id}/sources/upload",
    response_model=SourceOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_source(
    notebook: Notebook = Depends(get_notebook),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    inference: InferenceAdapter = Depends(get_inference),
) -> SourceOut:
    filename = file.filename or "upload.bin"
    data = await file.read()
    try:
        source = ingest_upload(
            db,
            settings=settings,
            inference=inference,
            notebook_id=notebook.id,
            filename=filename,
            data=data,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _source_out(db, source)


@router.post(
    "/notebooks/{notebook_id}/sources/paste",
    response_model=SourceOut,
    status_code=status.HTTP_201_CREATED,
)
def paste_source(
    body: PasteIn,
    notebook: Notebook = Depends(get_notebook),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    inference: InferenceAdapter = Depends(get_inference),
) -> SourceOut:
    source = ingest_paste(
        db,
        settings=settings,
        inference=inference,
        notebook_id=notebook.id,
        text=body.text,
        filename=body.filename,
    )
    return _source_out(db, source)
