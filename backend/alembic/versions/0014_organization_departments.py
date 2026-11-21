"""add single-level organization departments

Revision ID: 0014_org_departments
Revises: 0013_org_invite_admin
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0014_org_departments"
down_revision: Union[str, Sequence[str], None] = "0013_org_invite_admin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organization_departments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=140), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organization_departments")),
        sa.UniqueConstraint("organization_id", "id", name=op.f("uq_org_departments_org_id")),
        sa.UniqueConstraint("organization_id", "slug", name=op.f("uq_org_departments_org_slug")),
    )
    op.create_index("ix_org_departments_org_name", "organization_departments", ["organization_id", "name"])
    op.add_column("organization_memberships", sa.Column("department_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("org_membership_department_tenant"), "organization_memberships", "organization_departments",
        ["organization_id", "department_id"], ["organization_id", "id"], ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("org_membership_department_tenant"), "organization_memberships", type_="foreignkey")
    op.drop_column("organization_memberships", "department_id")
    op.drop_index("ix_org_departments_org_name", table_name="organization_departments")
    op.drop_table("organization_departments")
