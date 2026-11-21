"""track overdue accepted corporate assignments

Revision ID: 0015_assignment_overdue
Revises: 0014_org_departments
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015_assignment_overdue"
down_revision: Union[str, Sequence[str], None] = "0014_org_departments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("organization_course_assignments", sa.Column("overdue_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_org_assignments_overdue_due",
        "organization_course_assignments",
        ["status", "due_at"],
        postgresql_where=sa.text("overdue_at IS NULL AND status = 'accepted'"),
    )


def downgrade() -> None:
    op.drop_index("ix_org_assignments_overdue_due", table_name="organization_course_assignments")
    op.drop_column("organization_course_assignments", "overdue_at")
