"""Seed system roles, permissions and the initial RBAC matrix.

The data is intentionally duplicated here (instead of importing application
constants) so this revision stays reproducible even if `app/modules/users/rbac.py`
changes later.

Roles are additive: a user with several roles receives the union of their
permissions. `guest` is seeded for completeness but is never assigned to an
account — an unauthenticated request simply has no user.
"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import insert as pg_insert

revision = "0002_seed_rbac"
down_revision = "0001_users_rbac"
branch_labels = None
depends_on = None

ROLES: tuple[tuple[str, str, str], ...] = (
    ("guest", "Гость", "Неавторизованный посетитель. Роль не назначается аккаунтам."),
    ("user", "Пользователь", "Базовая роль каждого зарегистрированного аккаунта."),
    ("course_author", "Автор курсов", "Создание и публикация собственных курсов."),
    ("teacher", "Преподаватель", "Ведение обучения и проверка заданий."),
    ("organization_employee", "Сотрудник организации", "Обучение в рамках организации."),
    ("organization_manager", "Руководитель организации", "Управление сотрудниками и отчётами."),
    ("admin", "Администратор платформы", "Полный доступ к управлению платформой."),
)

PERMISSIONS: tuple[tuple[str, str], ...] = (
    ("profile:read", "Просмотр собственного профиля"),
    ("profile:update", "Изменение собственного профиля"),
    ("courses:read", "Просмотр каталога курсов"),
    ("courses:create", "Создание курсов"),
    ("courses:update", "Редактирование собственных курсов"),
    ("courses:publish", "Публикация курсов"),
    ("learning:enroll", "Запись на курсы"),
    ("learning:participate", "Прохождение обучения"),
    ("teaching:manage", "Ведение занятий и проверка заданий"),
    ("organization:view_members", "Просмотр сотрудников организации"),
    ("organization:manage_members", "Управление сотрудниками организации"),
    ("organization:view_reports", "Просмотр отчётов организации"),
    ("admin:manage_users", "Управление пользователями"),
    ("admin:manage_roles", "Управление ролями и разрешениями"),
    ("admin:manage_platform", "Управление платформой"),
)

ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "guest": (),
    "user": (
        "profile:read",
        "profile:update",
        "courses:read",
        "learning:enroll",
        "learning:participate",
    ),
    "course_author": (
        "profile:read",
        "profile:update",
        "courses:read",
        "courses:create",
        "courses:update",
        "courses:publish",
        "learning:participate",
    ),
    "teacher": (
        "profile:read",
        "profile:update",
        "courses:read",
        "learning:participate",
        "teaching:manage",
    ),
    "organization_employee": (
        "profile:read",
        "profile:update",
        "courses:read",
        "learning:enroll",
        "learning:participate",
    ),
    "organization_manager": (
        "profile:read",
        "profile:update",
        "courses:read",
        "learning:enroll",
        "learning:participate",
        "organization:view_members",
        "organization:manage_members",
        "organization:view_reports",
    ),
    "admin": tuple(code for code, _ in PERMISSIONS),
}

roles = sa.table(
    "roles",
    sa.column("id", sa.Uuid()),
    sa.column("code", sa.String()),
    sa.column("name", sa.String()),
    sa.column("description", sa.String()),
)

permissions = sa.table(
    "permissions",
    sa.column("id", sa.Uuid()),
    sa.column("code", sa.String()),
    sa.column("description", sa.String()),
)

role_permissions = sa.table(
    "role_permissions",
    sa.column("role_id", sa.Uuid()),
    sa.column("permission_id", sa.Uuid()),
)


def upgrade() -> None:
    bind = op.get_bind()

    op.execute(
        pg_insert(roles)
        .values(
            [
                {
                    "id": uuid.uuid4(),
                    "code": code,
                    "name": name,
                    "description": description,
                }
                for code, name, description in ROLES
            ]
        )
        .on_conflict_do_nothing(index_elements=["code"])
    )

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
    ]
    if links:
        op.execute(
            pg_insert(role_permissions).values(links).on_conflict_do_nothing(
                index_elements=["role_id", "permission_id"]
            )
        )


def downgrade() -> None:
    role_codes = [code for code, _, _ in ROLES]
    permission_codes = [code for code, _ in PERMISSIONS]

    seeded_role_ids = sa.select(roles.c.id).where(roles.c.code.in_(role_codes))
    seeded_permission_ids = sa.select(permissions.c.id).where(
        permissions.c.code.in_(permission_codes)
    )

    op.execute(
        role_permissions.delete().where(
            sa.or_(
                role_permissions.c.role_id.in_(seeded_role_ids),
                role_permissions.c.permission_id.in_(seeded_permission_ids),
            )
        )
    )
    op.execute(permissions.delete().where(permissions.c.code.in_(permission_codes)))
    op.execute(roles.delete().where(roles.c.code.in_(role_codes)))
