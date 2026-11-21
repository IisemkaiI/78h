"""allow multiple active owners per organization

Revision ID: 0011_org_multi_owner
Revises: 0010_organizations
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_org_multi_owner"
down_revision: Union[str, Sequence[str], None] = "0010_organizations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("uq_organization_memberships_active_owner", table_name="organization_memberships")


def downgrade() -> None:
    duplicate_owner_organization = op.get_bind().execute(sa.text(
        "SELECT organization_id FROM organization_memberships "
        "WHERE role = 'owner' AND status = 'active' "
        "GROUP BY organization_id HAVING count(*) > 1 LIMIT 1"
    )).scalar_one_or_none()
    if duplicate_owner_organization is not None:
        raise RuntimeError(
            "Cannot downgrade 0011_org_multi_owner while an organization has "
            "multiple active owners; transfer ownership first. No memberships were changed."
        )
    op.create_index(
        "uq_organization_memberships_active_owner",
        "organization_memberships",
        ["organization_id"],
        unique=True,
        postgresql_where=sa.text("role = 'owner' AND status = 'active'"),
    )
