"""Application configuration.

All values are read from environment variables (see `.env.example` in the
project root). The root `.env` file is shared with Docker Compose so that
PostgreSQL credentials are defined in exactly one place.

Secrets are never exposed through the API: connection details are only used
internally to build the database DSN.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> backend/app/core -> backend/app -> backend -> <project root>
PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Runtime settings of the backend service."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application -------------------------------------------------------
    project_name: str = "Education Platform"
    project_version: str = "0.1.0"
    app_env: Literal["local", "test", "staging", "production"] = "local"
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # --- API ---------------------------------------------------------------
    api_v1_prefix: str = "/api/v1"
    # Comma-separated list, e.g. "http://localhost:5173,http://127.0.0.1:5173"
    # Defaults: Vite dev server (5173) and `npm run preview` (4173) on IPv4/IPv6 names.
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:4173,http://127.0.0.1:4173"
    )

    # --- PostgreSQL --------------------------------------------------------
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_user: str = "edu_platform"
    postgres_password: SecretStr = SecretStr("")
    postgres_db: str = "education_platform"

    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_connect_timeout: int = 5
    db_ready_timeout: float = 3.0

    @property
    def cors_origins_list(self) -> list[str]:
        """CORS origins parsed from the comma-separated setting."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def database_dsn(self) -> str:
        """Async SQLAlchemy DSN. Internal use only — never returned by the API."""
        return (
            f"postgresql+asyncpg://{quote(self.postgres_user, safe='')}:"
            f"{quote(self.postgres_password.get_secret_value(), safe='')}@"
            f"{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance (single read of the environment per process)."""
    return Settings()
