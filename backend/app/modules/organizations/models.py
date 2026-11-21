"""Organization, membership, invitation and course-assignment records.

This module owns corporate lifecycle data only. Course progress and enrollment
remain owned by the learning module and are referenced, never duplicated.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint("status IN ('active','suspended','archived')", name="status_values"),
        Index("ix_organizations_status_created", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(180), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'active'"))
    created_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC), nullable=False,
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OrganizationDepartment(Base):
    """A single-level department owned by exactly one organization."""

    __tablename__ = "organization_departments"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_org_departments_org_id"),
        UniqueConstraint("organization_id", "slug", name="uq_org_departments_org_slug"),
        Index("ix_org_departments_org_name", "organization_id", "name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(UTC), nullable=False
    )


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        CheckConstraint("role IN ('owner','admin','manager','employee')", name="role_values"),
        CheckConstraint("status IN ('active','suspended','removed')", name="status_values"),
        UniqueConstraint("organization_id", "user_id", name="uq_organization_memberships_org_user"),
        # Supports composite foreign keys that make cross-tenant references impossible.
        UniqueConstraint("organization_id", "id", name="uq_organization_memberships_org_id"),
        ForeignKeyConstraint(
            ["organization_id", "department_id"],
            ["organization_departments.organization_id", "organization_departments.id"],
            name="org_membership_department_tenant",
            ondelete="RESTRICT",
        ),
        Index("ix_organization_memberships_user_status", "user_id", "status"),
        Index("ix_organization_memberships_org_status_role", "organization_id", "status", "role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    department_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'active'"))
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(UTC), nullable=False
    )


class OrganizationInvitation(Base):
    __tablename__ = "organization_invitations"
    __table_args__ = (
        CheckConstraint("role IN ('admin','manager','employee')", name="role_values"),
        CheckConstraint("length(email_normalized) BETWEEN 3 AND 320", name="email_length"),
        CheckConstraint("length(token_hash) = 64", name="token_hash_length"),
        ForeignKeyConstraint(
            ["organization_id", "invited_by_membership_id"],
            ["organization_memberships.organization_id", "organization_memberships.id"],
            name="org_invites_org_membership",
            ondelete="RESTRICT",
        ),
        Index("ix_organization_invitations_org_expiry", "organization_id", "expires_at"),
        Index("uq_organization_invitations_token_hash", "token_hash", unique=True),
        Index(
            "uq_organization_invitations_open_email",
            "organization_id",
            "email_normalized",
            unique=True,
            postgresql_where=text("accepted_at IS NULL AND revoked_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    invited_by_membership_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    email_normalized: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(UTC), nullable=False
    )


class OrganizationCourseAssignment(Base):
    __tablename__ = "organization_course_assignments"
    __table_args__ = (
        CheckConstraint("status IN ('pending','accepted','declined','cancelled')", name="status_values"),
        CheckConstraint("round_number > 0", name="round_number_positive"),
        UniqueConstraint(
            "organization_id", "membership_id", "course_id", "round_number",
            name="uq_organization_course_assignments_cycle",
        ),
        ForeignKeyConstraint(
            ["organization_id", "membership_id"],
            ["organization_memberships.organization_id", "organization_memberships.id"],
            name="org_assignments_org_member",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "assigned_by_membership_id"],
            ["organization_memberships.organization_id", "organization_memberships.id"],
            name="org_assignments_org_assigner",
            ondelete="RESTRICT",
        ),
        Index("ix_organization_course_assignments_org_status_due", "organization_id", "status", "due_at"),
        Index("ix_organization_course_assignments_member_status", "membership_id", "status"),
        Index("ix_organization_course_assignments_course_status", "course_id", "status"),
        Index("ix_organization_course_assignments_enrollment", "enrollment_id"),
        Index(
            "ix_org_assignments_overdue_due", "status", "due_at",
            postgresql_where=text("overdue_at IS NULL AND status = 'accepted'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    membership_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    assigned_by_membership_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False
    )
    enrollment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("enrollments.id", ondelete="RESTRICT")
    )
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    is_required: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(UTC), nullable=False
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    declined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    overdue_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
