"""Request and response schemas for organization membership APIs."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing_extensions import Annotated

OrganizationRole = Literal["owner", "admin", "manager", "employee"]
MemberRole = Literal["owner", "admin", "manager", "employee"]
InvitationRole = Literal["admin", "manager", "employee"]
OrganizationSlug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", min_length=2, max_length=180)]


class OrganizationCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=160)]
    slug: OrganizationSlug


class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    status: str
    created_by_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None


class MembershipRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    display_name: str
    email: str
    role: OrganizationRole
    status: str
    joined_at: datetime | None
    created_at: datetime
    can_update_role: bool = False
    can_remove: bool = False
    department_id: uuid.UUID | None = None


class DepartmentCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]


class DepartmentUpdate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]


class DepartmentRead(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    slug: str
    members_count: int = 0


class MemberDepartmentUpdate(BaseModel):
    department_id: uuid.UUID | None = None


class MembershipRoleUpdate(BaseModel):
    role: MemberRole


class OrganizationList(BaseModel):
    items: list[OrganizationRead] = Field(default_factory=list)


class InvitationCreate(BaseModel):
    email: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=320)]
    role: InvitationRole


class InvitationRead(BaseModel):
    id: uuid.UUID
    email: str
    role: InvitationRole
    status: Literal["pending", "accepted", "revoked", "expired"]
    expires_at: datetime
    created_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None


class InvitationCreated(InvitationRead):
    status: Literal["pending"] = "pending"
    token: str


class InvitationList(BaseModel):
    items: list[InvitationRead] = Field(default_factory=list)


class InvitationAccept(BaseModel):
    token: Annotated[str, StringConstraints(min_length=32, max_length=128)]


class InvitationAccepted(BaseModel):
    invitation_id: uuid.UUID
    organization_id: uuid.UUID
    membership_id: uuid.UUID
    role: OrganizationRole
    joined_at: datetime


class CourseAssignmentBulkCreate(BaseModel):
    course_id: uuid.UUID
    membership_ids: Annotated[list[uuid.UUID], Field(min_length=1, max_length=500)]
    due_at: datetime | None = None
    is_required: bool = True


class CourseAssignmentRead(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    membership_id: uuid.UUID
    learner_user_id: uuid.UUID
    learner_name: str
    department_id: uuid.UUID | None = None
    course_id: uuid.UUID
    course_title: str
    enrollment_id: uuid.UUID | None
    enrollment_status: str | None
    progress_percent: int | None
    is_course_completed: bool | None
    status: Literal["pending", "accepted", "declined", "cancelled"]
    is_required: bool
    due_at: datetime | None
    assigned_at: datetime
    accepted_at: datetime | None
    declined_at: datetime | None
    cancelled_at: datetime | None
    overdue_at: datetime | None = None


class CourseAssignmentList(BaseModel):
    items: list[CourseAssignmentRead]
    total: int


class OrganizationLearningStats(BaseModel):
    assignments_total: int
    pending: int
    accepted: int
    declined: int
    cancelled: int
    learners_total: int
    active_enrollments: int
    completed_enrollments: int
    average_progress_percent: int
