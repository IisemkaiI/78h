"""corporate organizations, membership, invitations and assignments

Revision ID: 0010_organizations
Revises: 0009_notifications
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_organizations"
down_revision: Union[str, Sequence[str], None] = "0009_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'active'"), nullable=False),
        sa.Column("created_by_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('active','suspended','archived')", name="ck_organizations_status_values"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_organizations_created_by_id_users", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_organizations"),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )
    op.create_index("ix_organizations_status_created", "organizations", ["status", "created_at"])

    op.create_table(
        "organization_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'active'"), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("role IN ('owner','manager','employee')", name="ck_organization_memberships_role_values"),
        sa.CheckConstraint("status IN ('active','suspended','removed')", name="ck_organization_memberships_status_values"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], name="fk_organization_memberships_organization_id_organizations", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_organization_memberships_user_id_users", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_organization_memberships"),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_organization_memberships_org_user"),
        sa.UniqueConstraint("organization_id", "id", name="uq_organization_memberships_org_id"),
    )
    op.create_index("ix_organization_memberships_user_status", "organization_memberships", ["user_id", "status"])
    op.create_index("ix_organization_memberships_org_status_role", "organization_memberships", ["organization_id", "status", "role"])
    op.create_index(
        "uq_organization_memberships_active_owner",
        "organization_memberships",
        ["organization_id"],
        unique=True,
        postgresql_where=sa.text("role = 'owner' AND status = 'active'"),
    )

    op.create_table(
        "organization_invitations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("invited_by_membership_id", sa.Uuid(), nullable=False),
        sa.Column("email_normalized", sa.String(length=320), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("role IN ('manager','employee')", name="ck_organization_invitations_role_values"),
        sa.CheckConstraint("length(email_normalized) BETWEEN 3 AND 320", name="ck_organization_invitations_email_length"),
        sa.CheckConstraint("length(token_hash) = 64", name="ck_organization_invitations_token_hash_length"),
        sa.ForeignKeyConstraint(
            ["organization_id", "invited_by_membership_id"],
            ["organization_memberships.organization_id", "organization_memberships.id"],
            name="org_invites_org_membership",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_organization_invitations"),
    )
    op.create_index("ix_organization_invitations_org_expiry", "organization_invitations", ["organization_id", "expires_at"])
    op.create_index("uq_organization_invitations_token_hash", "organization_invitations", ["token_hash"], unique=True)
    op.create_index(
        "uq_organization_invitations_open_email",
        "organization_invitations",
        ["organization_id", "email_normalized"],
        unique=True,
        postgresql_where=sa.text("accepted_at IS NULL AND revoked_at IS NULL"),
    )

    op.create_table(
        "organization_course_assignments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("membership_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_by_membership_id", sa.Uuid(), nullable=False),
        sa.Column("course_id", sa.Uuid(), nullable=False),
        sa.Column("enrollment_id", sa.Uuid(), nullable=True),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("is_required", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("declined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('pending','accepted','declined','cancelled')", name="ck_organization_course_assignments_status_values"),
        sa.CheckConstraint("round_number > 0", name="ck_organization_course_assignments_round_number_positive"),
        sa.ForeignKeyConstraint(
            ["organization_id", "membership_id"],
            ["organization_memberships.organization_id", "organization_memberships.id"],
            name="org_assignments_org_member",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "assigned_by_membership_id"],
            ["organization_memberships.organization_id", "organization_memberships.id"],
            name="org_assignments_org_assigner",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], name="fk_organization_course_assignments_course_id_courses", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["enrollment_id"], ["enrollments.id"], name="fk_organization_course_assignments_enrollment_id_enrollments", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_organization_course_assignments"),
        sa.UniqueConstraint("organization_id", "membership_id", "course_id", "round_number", name="uq_organization_course_assignments_cycle"),
    )
    op.create_index("ix_organization_course_assignments_org_status_due", "organization_course_assignments", ["organization_id", "status", "due_at"])
    op.create_index("ix_organization_course_assignments_member_status", "organization_course_assignments", ["membership_id", "status"])
    op.create_index("ix_organization_course_assignments_course_status", "organization_course_assignments", ["course_id", "status"])
    op.create_index("ix_organization_course_assignments_enrollment", "organization_course_assignments", ["enrollment_id"])


def downgrade() -> None:
    op.drop_index("ix_organization_course_assignments_enrollment", table_name="organization_course_assignments")
    op.drop_index("ix_organization_course_assignments_course_status", table_name="organization_course_assignments")
    op.drop_index("ix_organization_course_assignments_member_status", table_name="organization_course_assignments")
    op.drop_index("ix_organization_course_assignments_org_status_due", table_name="organization_course_assignments")
    op.drop_table("organization_course_assignments")

    op.drop_index("uq_organization_invitations_open_email", table_name="organization_invitations")
    op.drop_index("uq_organization_invitations_token_hash", table_name="organization_invitations")
    op.drop_index("ix_organization_invitations_org_expiry", table_name="organization_invitations")
    op.drop_table("organization_invitations")

    op.drop_index("uq_organization_memberships_active_owner", table_name="organization_memberships")
    op.drop_index("ix_organization_memberships_org_status_role", table_name="organization_memberships")
    op.drop_index("ix_organization_memberships_user_status", table_name="organization_memberships")
    op.drop_table("organization_memberships")

    op.drop_index("ix_organizations_status_created", table_name="organizations")
    op.drop_table("organizations")
