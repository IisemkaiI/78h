"""allow organization admins as invitation targets

Revision ID: 0013_org_invite_admin
Revises: 0012_org_scoped_admin
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013_org_invite_admin"
down_revision: Union[str, Sequence[str], None] = "0012_org_scoped_admin"
branch_labels = None
depends_on = None


def _role_check_name() -> str:
    name = op.get_bind().execute(sa.text(
        "SELECT c.conname FROM pg_constraint c "
        "JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey) "
        "WHERE c.conrelid = 'organization_invitations'::regclass "
        "AND c.contype = 'c' AND a.attname = 'role' LIMIT 1"
    )).scalar_one_or_none()
    if name is None:
        raise RuntimeError("Organization invitation role check constraint was not found.")
    return str(name)


def upgrade() -> None:
    op.drop_constraint(op.f(_role_check_name()), "organization_invitations", type_="check")
    op.create_check_constraint(
        op.f("ck_organization_invitations_role_values"),
        "organization_invitations",
        "role IN ('admin','manager','employee')",
    )


def downgrade() -> None:
    admin_invitations = op.get_bind().execute(sa.text(
        "SELECT count(*) FROM organization_invitations WHERE role = 'admin'"
    )).scalar_one()
    if admin_invitations:
        raise RuntimeError(
            "Cannot downgrade 0013_org_invite_admin while admin invitations exist; "
            "remove those invitation records first. No invitation data was changed."
        )
    op.drop_constraint(op.f(_role_check_name()), "organization_invitations", type_="check")
    op.create_check_constraint(
        op.f("ck_organization_invitations_role_values"),
        "organization_invitations",
        "role IN ('manager','employee')",
    )
