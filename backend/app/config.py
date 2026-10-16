"""
Application settings module.

All settings are loaded from environment variables (via pydantic-settings).
Secrets (passwords, JWT key) are accessed through SecretsProvider so that
future backends (Vault, HSM) require zero call-site changes (FR-004,
Constitution P9).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration for the PA Evidence Assistant backend.

    All values are read from environment variables or a .env file.
    Secrets are also surfaced through SecretsProvider in ``secrets.py``;
    this class holds them as plain attributes so FastAPI dependencies can
    access them without having to call SecretsProvider directly.
    """

    model_config = SettingsConfigDict(
        env_file="../docker/.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -----------------------------------------------------------------------
    # Database
    # -----------------------------------------------------------------------
    DATABASE_URL: str = (
        "postgresql+asyncpg://pa_app:changeme_dev_only@localhost:5432/pa_assistant"
    )

    # -----------------------------------------------------------------------
    # MinIO
    # -----------------------------------------------------------------------
    MINIO_ENDPOINT: str = "http://localhost:9000"
    MINIO_ACCESS_KEY: str = "pa_app"
    MINIO_SECRET_KEY: str = "changeme_dev_only"

    # -----------------------------------------------------------------------
    # Qdrant
    # -----------------------------------------------------------------------
    QDRANT_URL: str = "http://localhost:6333"

    # -----------------------------------------------------------------------
    # Text-Embeddings-Inference (TEI)
    # -----------------------------------------------------------------------
    TEI_URL: str = "http://localhost:8080"

    # -----------------------------------------------------------------------
    # Ollama (native on host — NEVER a public LLM API)
    # -----------------------------------------------------------------------
    OLLAMA_URL: str = "http://localhost:11434"

    # -----------------------------------------------------------------------
    # JWT / Auth
    # -----------------------------------------------------------------------
    JWT_SECRET_KEY: str = "changeme_generate_a_real_secret_before_use"
    JWT_ALGORITHM: Literal["HS256", "RS256"] = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # -----------------------------------------------------------------------
    # GPU / Hardware
    # -----------------------------------------------------------------------
    GPU_PRIORITY_POLICY: str = "llm_first"
    OCR_CPU_FALLBACK_TIMEOUT_SECONDS: float = 10.0
    VRAM_BUDGET_MB: int = 6144

    # -----------------------------------------------------------------------
    # Application tuning
    # -----------------------------------------------------------------------
    TURN_BUDGET: int = 10
    SLA_DEADLINE_HOURS: int = 24
    LOCK_EXPIRY_HOURS: int = 2

    # -----------------------------------------------------------------------
    # CORS / Dev
    # -----------------------------------------------------------------------
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    DEBUG: bool = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the (cached) settings singleton.

    Use as a FastAPI dependency::

        @app.get("/")
        def root(settings: Settings = Depends(get_settings)):
            ...
    """
    return Settings()
