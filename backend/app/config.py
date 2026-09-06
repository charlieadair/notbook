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
