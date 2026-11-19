"""Seed course categories and extend the RBAC matrix for authoring.

Adds two permissions to the existing model (no new role system):

* ``courses:delete`` — retire one's own course permanently;
* ``courses:manage_all`` — administrators manage every course.

``admin`` receives both, ``course_author`` receives ``courses:delete``.
Categories use their public slug as the idempotency key and are never removed
on upgrade.

Revision ID: 0004_seed_courses
Revises: 0003_courses
Create Date: 2026-11-19
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import insert as pg_insert

revision = "0004_seed_courses"
down_revision = "0003_courses"
branch_labels = None
depends_on = None

PERMISSIONS: tuple[tuple[str, str], ...] = (
    ("courses:delete", "Удаление собственных курсов"),
    ("courses:manage_all", "Управление всеми курсами платформы"),
)

ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "course_author": ("courses:delete",),
    "admin": ("courses:delete", "courses:manage_all"),
}

CATEGORIES: tuple[tuple[str, str, str], ...] = (
    ("programming", "Программирование", "Алгоритмы, языки и инженерные практики."),
    ("web-development", "Веб-разработка", "Frontend, backend и веб-платформы."),
    ("game-development", "Разработка игр", "Игровые движки, графика и геймдизайн."),
    ("design", "Дизайн", "UX/UI, графический дизайн и типографика."),
    (
        "information-technology",
        "Информационные технологии",
        "Инфраструктура, сети, безопасность и DevOps.",
    ),
    ("data-analytics", "Аналитика данных", "Данные, статистика и машинное обучение."),
    ("business-management", "Бизнес и управление", "Менеджмент, продукт и предпринимательство."),
    ("foreign-languages", "Иностранные языки", "Английский и другие языки для работы."),
)

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

categories = sa.table(
    "categories",
    sa.column("id", sa.Uuid()),
    sa.column("name", sa.String()),
    sa.column("slug", sa.String()),
    sa.column("description", sa.String()),
    sa.column("is_active", sa.Boolean()),
)


def upgrade() -> None:
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
    permission_ids = dict(bind.execute(sa.select(permissions.c.code, permissions.c.id)).all())
    links = [
        {"role_id": role_ids[role_code], "permission_id": permission_ids[permission_code]}
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

    op.execute(
        pg_insert(categories)
        .values(
            [
                {
                    "id": uuid.uuid4(),
                    "name": name,
                    "slug": slug,
                    "description": description,
                    "is_active": True,
                }
                for slug, name, description in CATEGORIES
            ]
        )
        .on_conflict_do_nothing(index_elements=["slug"])
    )


def downgrade() -> None:
    permission_codes = [code for code, _ in PERMISSIONS]
    category_slugs = [slug for slug, _, _ in CATEGORIES]

    seeded_permission_ids = sa.select(permissions.c.id).where(
        permissions.c.code.in_(permission_codes)
    )
    op.execute(
        role_permissions.delete().where(
            role_permissions.c.permission_id.in_(seeded_permission_ids)
        )
    )
    op.execute(permissions.delete().where(permissions.c.code.in_(permission_codes)))

    # Keep categories that authors already use: deleting them would fail on the
    # RESTRICT foreign key (and would silently destroy author data otherwise).
    slugs_sql = ", ".join(f"'{slug}'" for slug in category_slugs)
    op.execute(
        sa.text(
            "DELETE FROM categories "
            f"WHERE slug IN ({slugs_sql}) "
            "AND NOT EXISTS (SELECT 1 FROM courses WHERE courses.category_id = categories.id)"
        )
    )
