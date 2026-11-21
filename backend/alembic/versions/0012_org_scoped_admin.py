"""add scoped admin role to organization memberships

Revision ID: 0012_org_scoped_admin
Revises: 0011_org_multi_owner
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_org_scoped_admin"
down_revision: Union[str, Sequence[str], None] = "0011_org_multi_owner"
branch_labels = None
depends_on = None


def _role_check_name() -> str:
    name = op.get_bind().execute(sa.text(
        "SELECT c.conname FROM pg_constraint c "
        "JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey) "
        "WHERE c.conrelid = 'organization_memberships'::regclass "
        "AND c.contype = 'c' AND a.attname = 'role' LIMIT 1"
    )).scalar_one_or_none()
    if name is None:
        raise RuntimeError("Organization membership role check constraint was not found.")
    return str(name)


def upgrade() -> None:
    op.drop_constraint(op.f(_role_check_name()), "organization_memberships", type_="check")
    op.create_check_constraint(
        op.f("ck_organization_memberships_role_values"),
        "organization_memberships",
        "role IN ('owner','admin','manager','employee')",
    )


def downgrade() -> None:
    admin_memberships = op.get_bind().exec_driver_sql(
        "SELECT count(*) FROM organization_memberships WHERE role = 'admin'"
    ).scalar_one()
    if admin_memberships:
        raise RuntimeError(
            "Cannot downgrade 0012_org_scoped_admin while scoped admin memberships exist; "
            "reassign those members first. No memberships were changed."
        )
    op.drop_constraint(op.f(_role_check_name()), "organization_memberships", type_="check")
    op.create_check_constraint(
        op.f("ck_organization_memberships_role_values"),
        "organization_memberships",
        "role IN ('owner','manager','employee')",
    )
