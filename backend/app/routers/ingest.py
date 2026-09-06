from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import get_db
from app.deps import chunk_count_for, get_inference, get_notebook, get_settings
from app.inference.base import InferenceAdapter
from app.models import Notebook, Source
from app.schemas import PasteIn, SourceOut
from app.services.ingest import ingest_paste, ingest_upload

router = APIRouter(prefix="/api/v1", tags=["ingest"])


def _source_out(db: Session, source: Source) -> SourceOut:
    return SourceOut.model_validate(source).model_copy(
        update={"chunk_count": chunk_count_for(db, source.id)}
    )


def _ingest_upload_bytes(
    *,
    db: Session,
    settings: Settings,
    inference: InferenceAdapter,
    notebook_id: str,
    filename: str,
    data: bytes,
) -> SourceOut:
    try:
        source = ingest_upload(
            db,
            settings=settings,
            inference=inference,
            notebook_id=notebook_id,
            filename=filename,
            data=data,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _source_out(db, source)


def _ingest_paste_body(
    *,
    db: Session,
    settings: Settings,
    inference: InferenceAdapter,
    notebook_id: str,
    body: PasteIn,
) -> SourceOut:
    source = ingest_paste(
        db,
        settings=settings,
        inference=inference,
        notebook_id=notebook_id,
        text=body.text,
        filename=body.filename,
    )
    return _source_out(db, source)


@router.post(
    "/notebooks/{notebook_id}/sources",
    response_model=SourceOut,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a source (multipart upload or JSON paste)",
)
async def create_source(
    request: Request,
    notebook: Notebook = Depends(get_notebook),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    inference: InferenceAdapter = Depends(get_inference),
    kind: str | None = Query(default=None, description="paste | upload — optional hint"),
) -> SourceOut:
    """Content-Type discriminates: JSON paste `{filename?, text}` vs multipart `file`."""
    content_type = (request.headers.get("content-type") or "").lower()
    kind_norm = (kind or "").strip().lower()
    is_paste = kind_norm == "paste" or content_type.startswith("application/json")

    if is_paste:
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON paste body") from exc
        body = PasteIn.model_validate(payload)
        return _ingest_paste_body(
            db=db,
            settings=settings,
            inference=inference,
            notebook_id=notebook.id,
            body=body,
        )

    if "multipart/form-data" in content_type or kind_norm in {"upload", "file"}:
        form = await request.form()
        upload = form.get("file")
        if upload is None or not hasattr(upload, "read"):
            raise HTTPException(status_code=400, detail="multipart field 'file' is required")
        data = await upload.read()
        filename = getattr(upload, "filename", None) or "upload.bin"
        return _ingest_upload_bytes(
            db=db,
            settings=settings,
            inference=inference,
            notebook_id=notebook.id,
            filename=filename,
            data=data,
        )

    raise HTTPException(
        status_code=400,
        detail="Send multipart file upload or JSON {filename?, text} (or ?kind=paste)",
    )


@router.post(
    "/notebooks/{notebook_id}/sources/upload",
    response_model=SourceOut,
    status_code=status.HTTP_201_CREATED,
    deprecated=True,
    summary="Alias of POST /sources (multipart)",
)
async def upload_source(
    notebook: Notebook = Depends(get_notebook),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    inference: InferenceAdapter = Depends(get_inference),
) -> SourceOut:
    return _ingest_upload_bytes(
        db=db,
        settings=settings,
        inference=inference,
        notebook_id=notebook.id,
        filename=file.filename or "upload.bin",
        data=await file.read(),
    )


@router.post(
    "/notebooks/{notebook_id}/sources/paste",
    response_model=SourceOut,
    status_code=status.HTTP_201_CREATED,
    deprecated=True,
    summary="Alias of POST /sources (JSON paste)",
)
def paste_source(
    body: PasteIn,
    notebook: Notebook = Depends(get_notebook),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    inference: InferenceAdapter = Depends(get_inference),
) -> SourceOut:
    return _ingest_paste_body(
        db=db,
        settings=settings,
        inference=inference,
        notebook_id=notebook.id,
        body=body,
    )
