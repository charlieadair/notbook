from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import Settings
from app.db import fts_index_chunk
from app.inference.base import InferenceAdapter
from app.models import Chunk, Source
from app.services.bounded import BoundedTimeoutError, run_with_timeout
from app.services.chunking import chunk_text
from app.services.embeddings import pack_embedding
from app.services.ocr import ocr_image
from app.services.pdf import extract_pdf_pages

logger = logging.getLogger(__name__)

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
MARKDOWN_EXTS = {".md", ".txt", ".markdown"}
PDF_EXTS = {".pdf"}


def safe_filename(name: str) -> str:
    base = Path(name).name
    cleaned = re.sub(r"[^\w.\- ]+", "_", base).strip() or "upload.bin"
    return cleaned[:200]


def classify_upload(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext in PDF_EXTS:
        return "pdf"
    if ext in IMAGE_EXTS:
        return "image"
    if ext in MARKDOWN_EXTS:
        return "markdown"
    raise ValueError(f"Unsupported file type: {ext or filename}")


def allowed_upload(filename: str) -> bool:
    ext = Path(filename).suffix.lower()
    return ext in PDF_EXTS | IMAGE_EXTS | MARKDOWN_EXTS


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _write_file(settings: Settings, notebook_id: str, source_id: str, filename: str, data: bytes) -> str:
    dest_dir = settings.files_dir / notebook_id
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{source_id}_{filename}"
    dest.write_bytes(data)
    return f"files/{notebook_id}/{dest.name}"


def _embed_chunks(
    inference: InferenceAdapter,
    pieces: list[str],
    *,
    timeout: float,
) -> list[bytes | None]:
    if not pieces:
        return []
    try:
        vectors = run_with_timeout(inference.embed, pieces, timeout=timeout)
    except BoundedTimeoutError:
        logger.warning(
            "Embedding timed out after %.1fs; storing chunks without vectors (FTS fallback)",
            timeout,
        )
        return [None] * len(pieces)
    except Exception:
        logger.exception("Embedding failed; storing chunks without vectors (FTS fallback)")
        return [None] * len(pieces)
    if len(vectors) != len(pieces):
        logger.error("Embedding count mismatch; storing chunks without vectors")
        return [None] * len(pieces)
    return [pack_embedding(v) for v in vectors]


def _persist_chunks(
    db: Session,
    *,
    notebook_id: str,
    source_id: str,
    pieces: list[tuple[str, dict]],
    inference: InferenceAdapter,
    embed_timeout: float,
) -> int:
    blobs = _embed_chunks(inference, [p[0] for p in pieces], timeout=embed_timeout)
    for (text, locator), blob in zip(pieces, blobs, strict=True):
        chunk = Chunk(
            id=str(uuid.uuid4()),
            source_id=source_id,
            notebook_id=notebook_id,
            text=text,
            embedding=blob,
            locator=locator,
        )
        db.add(chunk)
        db.flush()
        fts_index_chunk(db, chunk.id, text)
    return len(pieces)


def _extract_pdf_pages(abs_path: Path, settings: Settings) -> list[tuple[int, str]]:
    try:
        return run_with_timeout(
            extract_pdf_pages,
            abs_path,
            timeout=settings.pdf_extract_timeout_seconds,
            max_pages=settings.pdf_max_pages,
            max_chars=settings.pdf_max_chars,
        )
    except BoundedTimeoutError as exc:
        raise ValueError(
            f"PDF extract timed out after {settings.pdf_extract_timeout_seconds:g}s "
            "(malformed or overly complex PDF)"
        ) from exc


def _extract_pieces(source_type: str, abs_path: Path, settings: Settings) -> list[tuple[str, dict]]:
    if source_type == "pdf":
        pages = _extract_pdf_pages(abs_path, settings)
        pieces: list[tuple[str, dict]] = []
        order = 0
        for page_no, page_text in pages:
            page_chunks = chunk_text(page_text, page=page_no, order_start=order)
            pieces.extend(page_chunks)
            order += len(page_chunks)
        if not pieces:
            raise ValueError("PDF contained no extractable text")
        return pieces

    if source_type == "image":
        text = ocr_image(abs_path)
        pieces = chunk_text(text, region="full", order_start=0)
        if not pieces:
            raise ValueError("OCR produced no text")
        return pieces

    # markdown | paste
    text = abs_path.read_text(encoding="utf-8", errors="replace")
    pieces = chunk_text(text, order_start=0)
    if not pieces:
        raise ValueError("File contained no text")
    return pieces


def ingest_bytes(
    db: Session,
    *,
    settings: Settings,
    inference: InferenceAdapter,
    notebook_id: str,
    filename: str,
    source_type: str,
    data: bytes,
) -> Source:
    source_id = str(uuid.uuid4())
    filename = safe_filename(filename)
    raw_path = _write_file(settings, notebook_id, source_id, filename, data)
    abs_path = settings.data_dir / raw_path

    source = Source(
        id=source_id,
        notebook_id=notebook_id,
        filename=filename,
        type=source_type,
        raw_path=raw_path,
        extract_status="pending",
        error=None,
        created_at=_now(),
    )
    db.add(source)
    db.flush()

    try:
        pieces = _extract_pieces(source_type, abs_path, settings)
        _persist_chunks(
            db,
            notebook_id=notebook_id,
            source_id=source_id,
            pieces=pieces,
            inference=inference,
            embed_timeout=settings.embed_timeout_seconds,
        )
        source.extract_status = "ok"
        source.error = None
    except Exception as exc:
        logger.warning("Extract failed for source %s: %s", source_id, exc)
        source.extract_status = "failed"
        source.error = str(exc)[:2000]

    db.flush()
    return source


def ingest_upload(
    db: Session,
    *,
    settings: Settings,
    inference: InferenceAdapter,
    notebook_id: str,
    filename: str,
    data: bytes,
) -> Source:
    if not allowed_upload(filename):
        raise ValueError(
            "Unsupported file type. Accepted: pdf, md, txt, png, jpg, jpeg, webp"
        )
    return ingest_bytes(
        db,
        settings=settings,
        inference=inference,
        notebook_id=notebook_id,
        filename=filename,
        source_type=classify_upload(filename),
        data=data,
    )


def ingest_paste(
    db: Session,
    *,
    settings: Settings,
    inference: InferenceAdapter,
    notebook_id: str,
    text: str,
    filename: str | None,
) -> Source:
    name = safe_filename(filename or "paste.txt")
    if not Path(name).suffix:
        name = f"{name}.txt"
    return ingest_bytes(
        db,
        settings=settings,
        inference=inference,
        notebook_id=notebook_id,
        filename=name,
        source_type="paste",
        data=text.encode("utf-8"),
    )
