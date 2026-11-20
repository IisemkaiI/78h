"""Sprint 4: enrollments, lesson progress and the learning journal.

The migration is additive: existing users, courses and RBAC rows are unchanged.
Seven learning permissions are granted to roles idempotently; no roles are
assigned to users and no new roles are created.

Revision ID: 0005_learning
Revises: 0004_seed_courses
Create Date: 2026-11-20
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert

revision = "0005_learning"
down_revision = "0004_seed_courses"
branch_labels = None
depends_on = None

PERMISSIONS: tuple[tuple[str, str], ...] = (
    ("enrollments:create", "Записаться на опубликованный курс"),
    ("enrollments:read_own", "Читать свои записи на курсы"),
    ("enrollments:cancel_own", "Отменять свою запись на курс"),
    ("enrollments:manage_all", "Управлять любыми записями на курсы"),
    ("progress:read_own", "Читать свой прогресс обучения"),
    ("progress:update_own", "Отмечать прогресс своих уроков"),
    ("progress:manage_all", "Управлять прогрессом любых пользователей"),
)

ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "user": (
        "enrollments:create",
        "enrollments:read_own",
        "enrollments:cancel_own",
        "progress:read_own",
        "progress:update_own",
    ),
    "course_author": (
        "enrollments:create",
        "enrollments:read_own",
        "enrollments:cancel_own",
        "progress:read_own",
        "progress:update_own",
    ),
    "teacher": (
        "enrollments:create",
        "enrollments:read_own",
        "enrollments:cancel_own",
        "progress:read_own",
        "progress:update_own",
    ),
    "organization_employee": (
        "enrollments:create",
        "enrollments:read_own",
        "enrollments:cancel_own",
        "progress:read_own",
        "progress:update_own",
    ),
    "organization_manager": (
        "enrollments:create",
        "enrollments:read_own",
        "enrollments:cancel_own",
        "progress:read_own",
        "progress:update_own",
    ),
    "admin": tuple(code for code, _ in PERMISSIONS),
}

permissions = sa.table(
    "permissions",
    sa.column("id", sa.Uuid()),
    sa.column("code", sa.String()),
    sa.column("description", sa.String()),
)

roles = sa.table(
    "roles",
    sa.column("id", sa.Uuid()),
    sa.column("code", sa.String()),
)

role_permissions = sa.table(
    "role_permissions",
    sa.column("role_id", sa.Uuid()),
    sa.column("permission_id", sa.Uuid()),
)


def upgrade() -> None:
    op.create_table(
        "enrollments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column(
            "enrolled_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('active', 'cancelled')",
            name="status_values",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_enrollments_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            name="fk_enrollments_course_id_courses",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_enrollments"),
        sa.UniqueConstraint(
            "user_id",
            "course_id",
            name="uq_enrollments_user_id_course_id",
        ),
    )
    op.create_index("ix_enrollments_user_id", "enrollments", ["user_id"], unique=False)
    op.create_index("ix_enrollments_course_id", "enrollments", ["course_id"], unique=False)
    op.create_index("ix_enrollments_status", "enrollments", ["status"], unique=False)

    op.create_table(
        "lesson_progress",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("enrollment_id", sa.Uuid(), nullable=False),
        sa.Column("lesson_id", sa.Uuid(), nullable=True),
        sa.Column("lesson_id_original", sa.Uuid(), nullable=False),
        sa.Column("module_id_original", sa.Uuid(), nullable=False),
        sa.Column("lesson_title_snapshot", sa.String(length=200), nullable=False),
        sa.Column("module_title_snapshot", sa.String(length=200), nullable=False),
        sa.Column(
            "state",
            sa.String(length=20),
            server_default=sa.text("'not_started'"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "state IN ('not_started', 'in_progress', 'completed')",
            name="state_values",
        ),
        sa.ForeignKeyConstraint(
            ["enrollment_id"],
            ["enrollments.id"],
            name="fk_lesson_progress_enrollment_id_enrollments",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["lesson_id"],
            ["lessons.id"],
            name="fk_lesson_progress_lesson_id_lessons",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_lesson_progress"),
        sa.UniqueConstraint(
            "enrollment_id",
            "lesson_id_original",
            name="uq_lesson_progress_enrollment_id_lesson_id_original",
        ),
    )
    op.create_index(
        "ix_lesson_progress_enrollment_id_state",
        "lesson_progress",
        ["enrollment_id", "state"],
        unique=False,
    )
    op.create_index(
        "ix_lesson_progress_lesson_id",
        "lesson_progress",
        ["lesson_id"],
        unique=False,
    )
    op.create_index(
        "ix_lesson_progress_lesson_id_original",
        "lesson_progress",
        ["lesson_id_original"],
        unique=False,
    )

    op.create_table(
        "learning_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("enrollment_id", sa.Uuid(), nullable=False),
        sa.Column("lesson_id", sa.Uuid(), nullable=True),
        sa.Column("lesson_id_original", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column(
            "payload",
            JSONB(),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "event_type IN ('enrolled', 'cancelled', 'reactivated', 'started', "
            "'lesson_started', 'lesson_completed', 'lesson_reopened', "
            "'lesson_reset', 'course_completed', 'course_reopened')",
            name="event_type_values",
        ),
        sa.ForeignKeyConstraint(
            ["enrollment_id"],
            ["enrollments.id"],
            name="fk_learning_events_enrollment_id_enrollments",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["lesson_id"],
            ["lessons.id"],
            name="fk_learning_events_lesson_id_lessons",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_learning_events"),
    )
    op.create_index(
        "ix_learning_events_enrollment_id_created_at",
        "learning_events",
        ["enrollment_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_learning_events_lesson_id",
        "learning_events",
        ["lesson_id"],
        unique=False,
    )

    bind = op.get_bind()
    op.execute(
        pg_insert(permissions)
        .values(
            [
                {"id": uuid.uuid4(), "code": code, "description": description}
                for code, description in PERMISSIONS
            ]
        )
        .on_conflict_do_nothing(index_elements=["code"])
    )

    role_ids = dict(bind.execute(sa.select(roles.c.code, roles.c.id)).all())
    permission_ids = dict(
        bind.execute(sa.select(permissions.c.code, permissions.c.id)).all()
    )
    links = [
        {
            "role_id": role_ids[role_code],
            "permission_id": permission_ids[permission_code],
        }
        for role_code, permission_codes in ROLE_PERMISSIONS.items()
        for permission_code in permission_codes
        if role_code in role_ids and permission_code in permission_ids
    ]
    if links:
        op.execute(
            pg_insert(role_permissions)
            .values(links)
            .on_conflict_do_nothing(index_elements=["role_id", "permission_id"])
        )


def downgrade() -> None:
    permission_codes = [code for code, _ in PERMISSIONS]
    seeded_permission_ids = sa.select(permissions.c.id).where(
        permissions.c.code.in_(permission_codes)
    )
    op.execute(
        role_permissions.delete().where(
            role_permissions.c.permission_id.in_(seeded_permission_ids)
        )
    )
    op.execute(permissions.delete().where(permissions.c.code.in_(permission_codes)))

    op.drop_index("ix_learning_events_lesson_id", table_name="learning_events")
    op.drop_index(
        "ix_learning_events_enrollment_id_created_at",
        table_name="learning_events",
    )
    op.drop_table("learning_events")

    op.drop_index(
        "ix_lesson_progress_lesson_id_original",
        table_name="lesson_progress",
    )
    op.drop_index("ix_lesson_progress_lesson_id", table_name="lesson_progress")
    op.drop_index(
        "ix_lesson_progress_enrollment_id_state",
        table_name="lesson_progress",
    )
    op.drop_table("lesson_progress")

    op.drop_index("ix_enrollments_status", table_name="enrollments")
    op.drop_index("ix_enrollments_course_id", table_name="enrollments")
    op.drop_index("ix_enrollments_user_id", table_name="enrollments")
    op.drop_table("enrollments")
