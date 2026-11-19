"""Async SQLAlchemy 2 engine, session factory and database health check."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator

from sqlalchemy import MetaData, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_settings = get_settings()

# Deterministic constraint names keep Alembic migrations stable and readable.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

engine = create_async_engine(
    _settings.database_dsn,
    echo=_settings.debug,
    pool_pre_ping=True,
    pool_size=_settings.db_pool_size,
    max_overflow=_settings.db_max_overflow,
    pool_timeout=_settings.db_pool_timeout,
    connect_args={
        "timeout": _settings.db_connect_timeout,
        "server_settings": {"application_name": "education-platform-api"},
    },
)

SessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields a database session.

    Used by the user/auth modules; commits are handled by services.
    """
    async with SessionFactory() as session:
        yield session


class DatabaseUnavailableError(RuntimeError):
    """Raised when PostgreSQL cannot be reached."""


async def ping_database(timeout: float | None = None) -> float:
    """Run ``SELECT 1`` against PostgreSQL and return the round-trip in ms.

    Raises:
        DatabaseUnavailableError: if the database is unreachable or too slow.
    """
    limit = timeout if timeout is not None else _settings.db_ready_timeout

    async def _probe() -> float:
        started = asyncio.get_running_loop().time()
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return (asyncio.get_running_loop().time() - started) * 1000

    try:
        return await asyncio.wait_for(_probe(), timeout=limit)
    except (TimeoutError, asyncio.TimeoutError) as exc:
        logger.warning("Database readiness check timed out after %.1fs", limit)
        raise DatabaseUnavailableError("database readiness check timed out") from exc
    except Exception as exc:  # noqa: BLE001 - any driver/connection error means "not ready"
        logger.warning("Database readiness check failed: %s: %s", type(exc).__name__, exc)
        raise DatabaseUnavailableError(str(type(exc).__name__)) from exc


async def dispose_engine() -> None:
    """Close all pooled connections (application shutdown)."""
    await engine.dispose()
