from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import chunk_count_for, get_notebook
from app.models import Chunk, Notebook, Source
from app.schemas import ChunkDetail, ChunkPreview, SourceMeta, SourceOut

router = APIRouter(prefix="/api/v1", tags=["inspect"])

PREVIEW_CHARS = 500


def _source_out(db: Session, source: Source) -> SourceOut:
    return SourceOut.model_validate(source).model_copy(
        update={"chunk_count": chunk_count_for(db, source.id)}
    )


@router.get("/notebooks/{notebook_id}/sources", response_model=list[SourceOut])
def list_sources(
    notebook: Notebook = Depends(get_notebook),
    db: Session = Depends(get_db),
) -> list[SourceOut]:
    sources = list(
        db.scalars(
            select(Source)
            .where(Source.notebook_id == notebook.id)
            .order_by(Source.created_at.asc())
        ).all()
    )
    return [_source_out(db, s) for s in sources]


@router.get(
    "/notebooks/{notebook_id}/sources/{source_id}/chunks",
    response_model=list[ChunkPreview],
)
def list_source_chunks(
    source_id: str,
    notebook: Notebook = Depends(get_notebook),
    db: Session = Depends(get_db),
) -> list[ChunkPreview]:
    source = db.get(Source, source_id)
    if source is None or source.notebook_id != notebook.id:
        raise HTTPException(status_code=404, detail="Source not found")
    chunks = list(
        db.scalars(select(Chunk).where(Chunk.source_id == source_id)).all()
    )
    chunks.sort(key=lambda c: (c.locator or {}).get("order") or 0)
    return [
        ChunkPreview(
            id=c.id,
            source_id=c.source_id,
            locator=c.locator,
            text=c.text,
            text_preview=c.text[:PREVIEW_CHARS],
        )
        for c in chunks
    ]


@router.get("/chunks/{chunk_id}", response_model=ChunkDetail)
def get_chunk(chunk_id: str, db: Session = Depends(get_db)) -> ChunkDetail:
    chunk = db.get(Chunk, chunk_id)
    if chunk is None:
        raise HTTPException(status_code=404, detail="Chunk not found")
    source = db.get(Source, chunk.source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return ChunkDetail(
        id=chunk.id,
        source_id=chunk.source_id,
        notebook_id=chunk.notebook_id,
        text=chunk.text,
        locator=chunk.locator,
        source=SourceMeta(
            id=source.id,
            filename=source.filename,
            type=source.type,
            extract_status=source.extract_status,
            notebook_id=source.notebook_id,
        ),
    )
