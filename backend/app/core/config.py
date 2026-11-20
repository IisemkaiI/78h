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

from pydantic import SecretStr, field_validator
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
    project_version: str = "0.6.0"
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

    # --- Authentication / JWT ---------------------------------------------
    # No default on purpose: a secret must come from the environment.
    jwt_secret: SecretStr = SecretStr("")
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_issuer: str = "education-platform"
    access_token_expire_minutes: int = 60

    # Private PDF directory; it is not served by the frontend or API statics.
    certificates_storage_dir: Path = PROJECT_ROOT / "backend" / "var" / "certificates"
    public_frontend_url: str = "http://127.0.0.1:5173"

    @field_validator("jwt_secret")
    @classmethod
    def _require_strong_jwt_secret(cls, value: SecretStr) -> SecretStr:
        """Fail fast when the signing key is missing, weak or a placeholder."""
        secret = value.get_secret_value()
        if len(secret) < 32:
            raise ValueError(
                "JWT_SECRET must be set in .env and be at least 32 characters long. "
                'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        if "change_me" in secret.lower():
            raise ValueError(
                "JWT_SECRET still contains the placeholder value. Generate a real secret: "
                'python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        return value

    @field_validator("certificates_storage_dir")
    @classmethod
    def _resolve_certificate_storage(cls, value: Path) -> Path:
        """Resolve relative storage overrides from the repository root."""
        return value if value.is_absolute() else (PROJECT_ROOT / value).resolve()

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
