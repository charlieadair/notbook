from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, LargeBinary, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


class Notebook(Base):
    __tablename__ = "notebooks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    sources: Mapped[list["Source"]] = relationship(back_populates="notebook")


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    notebook_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)  # pdf|markdown|paste|image
    raw_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    extract_status: Mapped[str] = mapped_column(String(32), nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    notebook: Mapped[Notebook] = relationship(back_populates="sources")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="source")


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False
    )
    notebook_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    locator: Mapped[dict] = mapped_column(JSON, nullable=False)

    source: Mapped[Source] = relationship(back_populates="chunks")


Index("ix_sources_notebook_id", Source.notebook_id)
Index("ix_chunks_notebook_id", Chunk.notebook_id)
Index("ix_chunks_source_id", Chunk.source_id)

# Topic / Quiz / Attempt / TopicScore tables belong to Study-logic — do not add them here.
