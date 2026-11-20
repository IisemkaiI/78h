"""certificates

Revision ID: 0008_certificates
Revises: 0007_assessment_lesson_retention
Create Date: 2026-11-20

"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008_certificates"
down_revision: Union[str, Sequence[str], None] = "0007_assessment_lesson_retention"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CERTIFICATE_PERMISSIONS = (
    ("certificates:issue_self", "Request a certificate for own completed enrollment"),
    ("certificates:read_self", "List and download own certificates"),
)
CERTIFICATE_ROLES = (
    "user",
    "course_author",
    "teacher",
    "organization_employee",
    "organization_manager",
    "admin",
)


def upgrade() -> None:
    op.create_table(
        "certificates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("enrollment_id", sa.Uuid(), nullable=False),
        sa.Column("recipient_name", sa.String(length=120), nullable=False),
        sa.Column("course_title", sa.String(length=200), nullable=False),
        sa.Column("completion_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("certificate_number", sa.String(length=40), nullable=False),
        sa.Column("verification_code", sa.String(length=64), nullable=False),
        sa.Column(
            "template_version",
            sa.String(length=20),
            server_default="1",
            nullable=False,
        ),
        sa.Column("pdf_storage_key", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["enrollment_id"],
            ["enrollments.id"],
            name="fk_certificates_enrollment_id_enrollments",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_certificates"),
        sa.UniqueConstraint("enrollment_id", name="uq_certificates_enrollment_id"),
        sa.UniqueConstraint("certificate_number", name="uq_certificates_certificate_number"),
        sa.UniqueConstraint("verification_code", name="uq_certificates_verification_code"),
        sa.UniqueConstraint("pdf_storage_key", name="uq_certificates_pdf_storage_key"),
    )
    op.create_index("ix_certificates_issued_at", "certificates", ["issued_at"])

    bind = op.get_bind()
    roles = sa.table("roles", sa.column("id", sa.Uuid()), sa.column("code", sa.String()))
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

    permission_ids: dict[str, uuid.UUID] = {}
    for code, description in CERTIFICATE_PERMISSIONS:
        permission_id = bind.execute(
            sa.select(permissions.c.id).where(permissions.c.code == code)
        ).scalar_one_or_none()
        if permission_id is None:
            permission_id = uuid.uuid4()
            bind.execute(
                permissions.insert().values(
                    id=permission_id,
                    code=code,
                    description=description,
                )
            )
        permission_ids[code] = permission_id

    role_ids = dict(
        bind.execute(sa.select(roles.c.code, roles.c.id).where(roles.c.code.in_(CERTIFICATE_ROLES))).all()
    )
    for role_code, role_id in role_ids.items():
        for permission_id in permission_ids.values():
            exists = bind.execute(
                sa.select(role_permissions.c.role_id).where(
                    role_permissions.c.role_id == role_id,
                    role_permissions.c.permission_id == permission_id,
                )
            ).first()
            if exists is None:
                bind.execute(
                    role_permissions.insert().values(
                        role_id=role_id,
                        permission_id=permission_id,
                    )
                )


def downgrade() -> None:
    bind = op.get_bind()
    permissions = sa.table(
        "permissions",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
    )
    role_permissions = sa.table(
        "role_permissions",
        sa.column("role_id", sa.Uuid()),
        sa.column("permission_id", sa.Uuid()),
    )
    permission_ids = sa.select(permissions.c.id).where(
        permissions.c.code.in_([code for code, _ in CERTIFICATE_PERMISSIONS])
    )
    bind.execute(role_permissions.delete().where(role_permissions.c.permission_id.in_(permission_ids)))
    bind.execute(permissions.delete().where(permissions.c.code.in_([code for code, _ in CERTIFICATE_PERMISSIONS])))
    op.drop_index("ix_certificates_issued_at", table_name="certificates")
    op.drop_table("certificates")
