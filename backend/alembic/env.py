"""Alembic environment (async SQLAlchemy 2).

The database URL is taken from the application settings, so migrations always
target the same PostgreSQL instance as the API and no credentials live in
`alembic.ini`.
"""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.core.database import Base

# Importing the models registers every table on Base.metadata for autogenerate.
import app.modules.courses.models  # noqa: F401  (side-effect import)
import app.modules.learning.models  # noqa: F401  (side-effect import)
import app.modules.assessments.models  # noqa: F401  (side-effect import)
import app.modules.certificates.models  # noqa: F401  (side-effect import)
import app.modules.users.models  # noqa: F401  (side-effect import)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()

# `ALEMBIC_DATABASE_URL` lets the test suite migrate a dedicated database
# without touching the development one. Production deployments never set it.
_database_url = os.environ.get("ALEMBIC_DATABASE_URL") or settings.database_dsn
config.set_main_option("sqlalchemy.url", _database_url.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Render SQL without connecting (``alembic upgrade head --sql``)."""
    context.configure(
        url=_database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
