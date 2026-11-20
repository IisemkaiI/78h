"""Schema and seed checks for the Alembic migrations."""

from __future__ import annotations

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.modules.courses.models  # noqa: F401  (registers course metadata)
import app.modules.learning.models  # noqa: F401  (registers learning metadata)
import app.modules.assessments.models  # noqa: F401  (registers assessment metadata)
import app.modules.users.models  # noqa: F401  (registers user metadata)
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
        "categories",
        "courses",
        "course_modules",
        "lessons",
        "enrollments",
        "lesson_progress",
        "learning_events",
        "course_instructors",
        "quizzes",
        "quiz_questions",
        "quiz_attempts",
        "quiz_answers",
        "practical_assignments",
        "assignment_submissions",
        "submission_versions",
        "assignment_reviews",
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

    assert counts[RoleCode.USER] == 13
    assert counts[RoleCode.ADMIN] == 32
    assert counts[RoleCode.COURSE_AUTHOR] == 19
    assert counts[RoleCode.TEACHER] == 14
    assert counts[RoleCode.ORGANIZATION_EMPLOYEE] == 13
    assert counts[RoleCode.ORGANIZATION_MANAGER] == 16
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


async def test_course_categories_are_seeded(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        rows = (
            await session.execute(
                text("SELECT slug, is_active FROM categories ORDER BY slug")
            )
        ).all()

    slugs = [row[0] for row in rows]
    assert slugs == [
        "business-management",
        "data-analytics",
        "design",
        "foreign-languages",
        "game-development",
        "information-technology",
        "programming",
        "web-development",
    ]
    assert all(row[1] is True for row in rows)


async def test_course_check_constraints_exist(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        names = set(
            await session.scalars(
                text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE conname IN ("
                    "'ck_courses_status_values', "
                    "'ck_courses_level_values', "
                    "'ck_lessons_estimated_duration_minutes_non_negative', "
                    "'ck_enrollments_status_values', "
                    "'ck_lesson_progress_state_values', "
                    "'ck_learning_events_event_type_values'"
                    ")"
                )
            )
        )

    assert names == {
        "ck_courses_status_values",
        "ck_courses_level_values",
        "ck_lessons_estimated_duration_minutes_non_negative",
        "ck_enrollments_status_values",
        "ck_lesson_progress_state_values",
        "ck_learning_events_event_type_values",
    }


async def test_learning_permissions_are_seeded(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    expected = {
        "enrollments:create",
        "enrollments:read_own",
        "enrollments:cancel_own",
        "enrollments:manage_all",
        "progress:read_own",
        "progress:update_own",
        "progress:manage_all",
    }
    async with session_factory() as session:
        codes = set(
            await session.scalars(
                text("SELECT code FROM permissions WHERE code LIKE 'enrollments:%' "
                     "OR code LIKE 'progress:%'")
            )
        )
        legacy = set(
            await session.scalars(
                text("SELECT code FROM permissions WHERE code IN "
                     "('learning:enroll', 'learning:participate')")
            )
        )
        assignments = await session.scalar(
            text(
                "SELECT count(*) FROM user_roles ur "
                "JOIN roles r ON r.id = ur.role_id "
                "WHERE r.code = 'admin'"
            )
        )

    assert codes == expected
    assert legacy == {"learning:enroll", "learning:participate"}
    assert assignments == 0


async def test_learning_foreign_keys_preserve_history(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT conname, confdeltype FROM pg_constraint "
                    "WHERE conname IN ("
                    "'fk_lesson_progress_lesson_id_lessons', "
                    "'fk_learning_events_lesson_id_lessons', "
                    "'fk_enrollments_course_id_courses'"
                    ")"
                )
            )
        ).all()

    actions = {
        name: action.decode() if isinstance(action, bytes) else action
        for name, action in rows
    }
    assert actions == {
        "fk_lesson_progress_lesson_id_lessons": "n",
        "fk_learning_events_lesson_id_lessons": "n",
        "fk_enrollments_course_id_courses": "r",
    }
