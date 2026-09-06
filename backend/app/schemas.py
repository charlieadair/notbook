from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NotebookCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)


class NotebookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    created_at: datetime


class Locator(BaseModel):
    page: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    order: int | None = None
    region: str | None = None


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    notebook_id: str
    filename: str
    type: str
    raw_path: str
    extract_status: str
    error: str | None = None
    created_at: datetime
    chunk_count: int = 0


class PasteIn(BaseModel):
    filename: str | None = None
    text: str = Field(min_length=1)


class ChunkOut(BaseModel):
    id: str
    source_id: str
    text: str
    locator: dict[str, Any]


class ChunkPreview(BaseModel):
    id: str
    source_id: str
    locator: dict[str, Any]
    text: str
    text_preview: str


class SourceMeta(BaseModel):
    id: str
    filename: str
    type: str
    extract_status: str
    notebook_id: str


class ChunkDetail(BaseModel):
    id: str
    source_id: str
    notebook_id: str
    text: str
    locator: dict[str, Any]
    source: SourceMeta


class RetrieveIn(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=8, ge=1, le=50)


class RetrieveChunk(BaseModel):
    id: str
    source_id: str
    text: str
    locator: dict[str, Any]
    score: float
    source_filename: str | None = None


class RetrieveOut(BaseModel):
    chunks: list[RetrieveChunk]


class HealthOut(BaseModel):
    status: str
    service: str = "notbook-study-api"


class InferenceInfoOut(BaseModel):
    adapter: str
    embed_model: str | None = None
    chat_model: str | None = None
