"""Schema and seed checks for the Alembic migrations."""

from __future__ import annotations

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.modules.users.models  # noqa: F401  (registers metadata for the diff check)
from app.core.database import Base
from app.modules.users.rbac import RoleCode
from tests.integration.conftest import BACKEND_DIR

pytestmark = pytest.mark.integration


async def test_database_is_at_alembic_head(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    head = ScriptDirectory.from_config(config).get_current_head()

    async with session_factory() as session:
        applied = await session.scalar(text("SELECT version_num FROM alembic_version"))

    assert applied == head


async def test_expected_tables_exist(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        rows = await session.scalars(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' ORDER BY table_name"
            )
        )
        tables = set(rows)

    assert {
        "users",
        "roles",
        "permissions",
        "user_roles",
        "role_permissions",
        "alembic_version",
    } <= tables


async def test_all_roles_are_seeded(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        codes = set(await session.scalars(text("SELECT code FROM roles")))

    assert codes == set(RoleCode.ALL)
    assert len(codes) == 7


async def test_guest_role_is_never_assigned(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        assignments = await session.scalar(
            text(
                "SELECT count(*) FROM user_roles ur "
                "JOIN roles r ON r.id = ur.role_id WHERE r.code = :code"
            ),
            {"code": RoleCode.GUEST},
        )
        guest_permissions = await session.scalar(
            text(
                "SELECT count(*) FROM role_permissions rp "
                "JOIN roles r ON r.id = rp.role_id WHERE r.code = :code"
            ),
            {"code": RoleCode.GUEST},
        )

    assert assignments == 0
    assert guest_permissions == 0


async def test_role_permission_matrix_is_seeded(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        counts = dict(
            (
                await session.execute(
                    text(
                        "SELECT r.code, count(rp.permission_id) FROM roles r "
                        "LEFT JOIN role_permissions rp ON rp.role_id = r.id "
                        "GROUP BY r.code"
                    )
                )
            ).all()
        )

    assert counts[RoleCode.USER] == 5
    assert counts[RoleCode.ADMIN] == 15
    assert counts[RoleCode.GUEST] == 0
    assert all(count > 0 for code, count in counts.items() if code != RoleCode.GUEST)


async def test_orm_metadata_matches_migrations(test_engine) -> None:
    """Autogenerate must not detect drift between models and the migrated schema."""
    async with test_engine.connect() as connection:
        diffs = await connection.run_sync(
            lambda sync_connection: compare_metadata(
                MigrationContext.configure(
                    sync_connection, opts={"compare_type": True}
                ),
                Base.metadata,
            )
        )

    assert diffs == []
