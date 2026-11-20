"""in-platform notifications

Revision ID: 0009_notifications
Revises: 0008_certificates
"""
from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_notifications"
down_revision: Union[str, Sequence[str], None] = "0008_certificates"
branch_labels = None
depends_on = None

PERMISSIONS = (
    ("notifications:read_own", "Read own notifications and unread count"),
    ("notifications:update_own", "Mark own notifications as read"),
)
ROLES = ("user", "course_author", "teacher", "organization_employee", "organization_manager", "admin")


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_event_key", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("type IN ('course_completed','quiz_completed','assignment_accepted','assignment_revision_required','certificate_issued')", name="ck_notifications_type_values"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_notifications_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_notifications"),
        sa.UniqueConstraint("user_id", "source_event_key", name="uq_notifications_user_event"),
    )
    op.create_index("ix_notifications_user_created", "notifications", ["user_id", "created_at", "id"])
    op.create_index("ix_notifications_user_unread", "notifications", ["user_id", "created_at"], postgresql_where=sa.text("read_at IS NULL"))
    bind = op.get_bind()
    roles = sa.table("roles", sa.column("id", sa.Uuid()), sa.column("code", sa.String()))
    permissions = sa.table("permissions", sa.column("id", sa.Uuid()), sa.column("code", sa.String()), sa.column("description", sa.String()))
    role_permissions = sa.table("role_permissions", sa.column("role_id", sa.Uuid()), sa.column("permission_id", sa.Uuid()))
    ids = {}
    for code, description in PERMISSIONS:
        pid = bind.execute(sa.select(permissions.c.id).where(permissions.c.code == code)).scalar_one_or_none()
        if pid is None:
            pid = uuid.uuid4()
            bind.execute(permissions.insert().values(id=pid, code=code, description=description))
        ids[code] = pid
    role_ids = dict(bind.execute(sa.select(roles.c.code, roles.c.id).where(roles.c.code.in_(ROLES))).all())
    for role_id in role_ids.values():
        for permission_id in ids.values():
            if bind.execute(sa.select(role_permissions.c.role_id).where(role_permissions.c.role_id == role_id, role_permissions.c.permission_id == permission_id)).first() is None:
                bind.execute(role_permissions.insert().values(role_id=role_id, permission_id=permission_id))


def downgrade() -> None:
    bind = op.get_bind()
    permissions = sa.table("permissions", sa.column("id", sa.Uuid()), sa.column("code", sa.String()))
    role_permissions = sa.table("role_permissions", sa.column("permission_id", sa.Uuid()))
    ids = sa.select(permissions.c.id).where(permissions.c.code.in_([code for code, _ in PERMISSIONS]))
    bind.execute(role_permissions.delete().where(role_permissions.c.permission_id.in_(ids)))
    bind.execute(permissions.delete().where(permissions.c.code.in_([code for code, _ in PERMISSIONS])) )
    op.drop_index("ix_notifications_user_unread", table_name="notifications")
    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_table("notifications")
