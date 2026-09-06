from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings. Secrets come from env only — never commit them."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    data_dir: Path = Field(
        default=Path("data"),
        validation_alias=AliasChoices("DATA_DIR", "NOTBOOK_DATA_DIR", "data_dir"),
    )
    # stub | openai-compatible | auto
    inference_adapter: str = Field(
        default="stub",
        validation_alias=AliasChoices(
            "INFERENCE_PROVIDER", "INFERENCE_ADAPTER", "inference_adapter"
        ),
    )
    openai_api_base: str | None = None
    openai_api_key: str | None = None
    openai_embed_model: str = Field(
        default="text-embedding-3-small",
        validation_alias=AliasChoices("EMBED_MODEL", "OPENAI_EMBED_MODEL", "openai_embed_model"),
    )
    openai_chat_model: str = Field(
        default="gpt-4o-mini",
        validation_alias=AliasChoices("CHAT_MODEL", "OPENAI_CHAT_MODEL", "openai_chat_model"),
    )
    # Hard bounds so ingest cannot hang the upload request (see #35).
    pdf_extract_timeout_seconds: float = Field(
        default=30.0,
        validation_alias=AliasChoices("PDF_EXTRACT_TIMEOUT_SECONDS", "pdf_extract_timeout_seconds"),
    )
    pdf_max_pages: int = Field(
        default=200,
        validation_alias=AliasChoices("PDF_MAX_PAGES", "pdf_max_pages"),
    )
    pdf_max_chars: int = Field(
        default=500_000,
        validation_alias=AliasChoices("PDF_MAX_CHARS", "pdf_max_chars"),
    )
    inference_connect_timeout_seconds: float = Field(
        default=10.0,
        validation_alias=AliasChoices(
            "INFERENCE_CONNECT_TIMEOUT_SECONDS", "inference_connect_timeout_seconds"
        ),
    )
    inference_read_timeout_seconds: float = Field(
        default=30.0,
        validation_alias=AliasChoices(
            "INFERENCE_READ_TIMEOUT_SECONDS", "inference_read_timeout_seconds"
        ),
    )
    embed_timeout_seconds: float = Field(
        default=30.0,
        validation_alias=AliasChoices("EMBED_TIMEOUT_SECONDS", "embed_timeout_seconds"),
    )
    # auto: LLM slices when a remote adapter is active, else heuristic windows.
    chunking_strategy: str = Field(
        default="auto",
        validation_alias=AliasChoices("CHUNKING_STRATEGY", "chunking_strategy"),
    )
    llm_chunk_timeout_seconds: float = Field(
        default=30.0,
        validation_alias=AliasChoices("LLM_CHUNK_TIMEOUT_SECONDS", "llm_chunk_timeout_seconds"),
    )
    llm_chunk_max_chars: int = Field(
        default=24_000,
        validation_alias=AliasChoices("LLM_CHUNK_MAX_CHARS", "llm_chunk_max_chars"),
    )
    llm_chunk_max_slices: int = Field(
        default=64,
        validation_alias=AliasChoices("LLM_CHUNK_MAX_SLICES", "llm_chunk_max_slices"),
    )

    @property
    def db_path(self) -> Path:
        return self.data_dir / "notbook.db"

    @property
    def files_dir(self) -> Path:
        return self.data_dir / "files"

    def resolved_adapter(self) -> str:
        """Default stub unless env explicitly configures a remote adapter."""
        name = (self.inference_adapter or "stub").strip().lower()
        if name in {"openai", "openai-compatible", "openai_compatible"}:
            return "openai-compatible"
        if name == "auto" and self.openai_api_base and self.openai_api_key:
            return "openai-compatible"
        return "stub"

    def uses_llm_chunking(self, inference_name: str | None) -> bool:
        """LLM path when strategy is llm, or auto + a non-stub remote adapter.

        Stub complete() is not a slicer — always heuristic so ingest stays offline.
        """
        strategy = (self.chunking_strategy or "auto").strip().lower()
        if strategy not in {"llm", "heuristic", "auto"}:
            strategy = "auto"
        if strategy == "heuristic":
            return False
        adapter = (inference_name or "").strip().lower()
        if adapter == "stub":
            return False
        if strategy == "llm":
            return True
        return adapter == "openai-compatible" or self.resolved_adapter() == "openai-compatible"
