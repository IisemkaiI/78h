"""Fixtures for tests that require a real PostgreSQL database.

The suite never touches the development database: a dedicated database
(``education_platform_test`` by default) is created, migrated with Alembic and
truncated between tests. Any other database engine would hide PostgreSQL-specific
behaviour, so SQLite is deliberately not used.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path
from urllib.parse import quote

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.database import get_session

BACKEND_DIR = Path(__file__).resolve().parents[2]
TEST_DB_NAME = os.getenv("TEST_POSTGRES_DB", "education_platform_test")


def test_database_dsn() -> str:
    """Async DSN of the dedicated test database."""
    settings = get_settings()
    return (
        f"postgresql+asyncpg://{quote(settings.postgres_user, safe='')}:"
        f"{quote(settings.postgres_password.get_secret_value(), safe='')}@"
        f"{settings.postgres_host}:{settings.postgres_port}/{TEST_DB_NAME}"
    )


def _create_database_if_missing() -> None:
    settings = get_settings()

    async def _create() -> None:
        connection = await asyncpg.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            user=settings.postgres_user,
            password=settings.postgres_password.get_secret_value(),
            database="postgres",
        )
        try:
            exists = await connection.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1", TEST_DB_NAME
            )
            if not exists:
                await connection.execute(f'CREATE DATABASE "{TEST_DB_NAME}"')
        finally:
            await connection.close()

    asyncio.run(_create())


@pytest.fixture(scope="session")
def migrated_database() -> None:
    """Create the test database and apply every Alembic migration to it."""
    _create_database_if_missing()

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    os.environ["ALEMBIC_DATABASE_URL"] = test_database_dsn()
    try:
        command.upgrade(config, "head")
    finally:
        os.environ.pop("ALEMBIC_DATABASE_URL", None)


@pytest.fixture(scope="session")
def test_engine(migrated_database: None):
    """Engine for the test database (NullPool: no connections shared across loops)."""
    engine = create_async_engine(test_database_dsn(), poolclass=NullPool)
    yield engine
    asyncio.run(engine.dispose())


@pytest.fixture(scope="session")
def session_factory(test_engine) -> async_sessionmaker[AsyncSession]:
    """Session factory bound to the test database."""
    return async_sessionmaker(test_engine, expire_on_commit=False, autoflush=False)


@pytest.fixture(autouse=True)
async def clean_database(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[None]:
    """Start every test from empty user/course tables; RBAC and categories stay seeded."""
    async with session_factory() as session:
        await session.execute(
            text(
                "TRUNCATE TABLE learning_events, lesson_progress, enrollments, "
                "lessons, course_modules, courses, user_roles, users CASCADE"
            )
        )
        await session.commit()
    yield


@pytest.fixture
async def client(
    app: object, session_factory: async_sessionmaker[AsyncSession]
) -> AsyncIterator[AsyncClient]:
    """HTTP client whose endpoints use the test database, not the dev one."""

    async def _session_override() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    dependency_app = app
    dependency_app.dependency_overrides[get_session] = _session_override  # type: ignore[attr-defined]
    transport = ASGITransport(app=dependency_app)  # type: ignore[arg-type]
    try:
        async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
            yield http_client
    finally:
        dependency_app.dependency_overrides.pop(get_session, None)  # type: ignore[attr-defined]
