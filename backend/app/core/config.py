from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    app_name: str = "AI Resume Analyzer"
    app_version: str = "1.0.0"
    api_prefix: str = "/api/v1"

    max_pdf_size_mb: int = 10
    cache_ttl_seconds: int = 3600
    redis_url: str | None = None

    ai_provider: str = "auto"
    gemini_api_key: str | None = None
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_model: str = "gemini-2.0-flash"

    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    ai_timeout_seconds: int = 45

    cors_origins: Annotated[list[str], NoDecode] = ["*"]

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, list):
            return value
        raw = value.strip()
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(origin).strip() for origin in parsed if str(origin).strip()]
            except json.JSONDecodeError:
                pass
        return [origin.strip() for origin in value.split(",") if origin.strip()]

    @field_validator("ai_provider")
    @classmethod
    def _validate_ai_provider(cls, value: str) -> str:
        allowed = {"auto", "gemini", "openai"}
        normalized = value.lower().strip()
        if normalized not in allowed:
            raise ValueError(f"ai_provider must be one of: {', '.join(sorted(allowed))}")
        return normalized


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
