"""Central configuration, loaded from environment / .env.

Everything the app needs to know about *which* backends to talk to lives here,
so switching Airtable <-> memory or OpenAI <-> stub is a one-line env change and
never a code change.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,  # allow Settings(app_api_key=...) as well as the env alias
    )

    # --- API auth ---
    app_api_key: str = Field(default="changeme-dev-key", alias="APP_API_KEY")

    # --- Director agent (Anthropic) ---
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    director_model: str = Field(default="claude-sonnet-5", alias="DIRECTOR_MODEL")

    # --- Persistence backend ---
    backend: Literal["memory", "airtable"] = Field(default="memory", alias="BACKEND")
    airtable_api_key: str | None = Field(default=None, alias="AIRTABLE_API_KEY")
    airtable_base_id: str | None = Field(default=None, alias="AIRTABLE_BASE_ID")

    # --- Image generation provider ---
    image_provider: Literal["openai", "stub"] = Field(default="stub", alias="IMAGE_PROVIDER")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")

    # --- Object storage ---
    storage_backend: Literal["local"] = Field(default="local", alias="STORAGE_BACKEND")
    storage_local_dir: str = Field(default="./.data/media", alias="STORAGE_LOCAL_DIR")


@lru_cache
def get_settings() -> Settings:
    """Cached accessor so the whole process shares one Settings instance."""
    return Settings()
