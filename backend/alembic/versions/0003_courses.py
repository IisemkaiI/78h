"""Sprint 2: categories, courses, modules and lessons.

Only additive DDL: existing users, roles and permissions are untouched.

Revision ID: 0003_courses
Revises: 0002_seed_rbac
Create Date: 2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_courses"
down_revision = "0002_seed_rbac"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=140), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
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
        sa.PrimaryKeyConstraint("id", name="pk_categories"),
        sa.UniqueConstraint("slug", name="uq_categories_slug"),
    )
    op.create_index("ix_categories_slug", "categories", ["slug"], unique=True)

    op.create_table(
        "courses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=220), nullable=False),
        sa.Column("short_description", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("cover_image_url", sa.String(length=500), nullable=True),
        sa.Column(
            "level",
            sa.String(length=20),
            server_default=sa.text("'beginner'"),
            nullable=False,
        ),
        sa.Column(
            "language",
            sa.String(length=10),
            server_default=sa.text("'ru'"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default=sa.text("'draft'"),
            nullable=False,
        ),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Uuid(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('draft', 'published', 'archived')",
            name="status_values",
        ),
        sa.CheckConstraint(
            "level IN ('beginner', 'intermediate', 'advanced')",
            name="level_values",
        ),
        sa.ForeignKeyConstraint(
            ["author_id"],
            ["users.id"],
            name="fk_courses_author_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name="fk_courses_category_id_categories",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_courses"),
        sa.UniqueConstraint("slug", name="uq_courses_slug"),
    )
    op.create_index("ix_courses_slug", "courses", ["slug"], unique=True)
    op.create_index("ix_courses_author_id", "courses", ["author_id"], unique=False)
    op.create_index("ix_courses_category_id", "courses", ["category_id"], unique=False)
    op.create_index(
        "ix_courses_status_published_at",
        "courses",
        ["status", "published_at"],
        unique=False,
    )

    op.create_table(
        "course_modules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("position", sa.Integer(), server_default=sa.text("1"), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["courses.id"],
            name="fk_course_modules_course_id_courses",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_course_modules"),
    )
    op.create_index(
        "ix_course_modules_course_id_position",
        "course_modules",
        ["course_id", "position"],
        unique=False,
    )

    op.create_table(
        "lessons",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("module_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("content", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("position", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "estimated_duration_minutes",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
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
            "estimated_duration_minutes >= 0",
            name="estimated_duration_minutes_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["module_id"],
            ["course_modules.id"],
            name="fk_lessons_module_id_course_modules",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_lessons"),
    )
    op.create_index(
        "ix_lessons_module_id_position",
        "lessons",
        ["module_id", "position"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_lessons_module_id_position", table_name="lessons")
    op.drop_table("lessons")
    op.drop_index("ix_course_modules_course_id_position", table_name="course_modules")
    op.drop_table("course_modules")
    op.drop_index("ix_courses_status_published_at", table_name="courses")
    op.drop_index("ix_courses_category_id", table_name="courses")
    op.drop_index("ix_courses_author_id", table_name="courses")
    op.drop_index("ix_courses_slug", table_name="courses")
    op.drop_table("courses")
    op.drop_index("ix_categories_slug", table_name="categories")
    op.drop_table("categories")
