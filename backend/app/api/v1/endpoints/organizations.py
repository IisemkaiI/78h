"""Organization and membership APIs with tenant-scoped authorization."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Response, status

from app.api.deps import SessionDep
from app.core.errors import ApiError
from app.modules.auth.dependencies import CurrentUser
from app.modules.organizations.course_assignments import OrganizationCourseAssignmentService
from app.modules.organizations.departments import OrganizationDepartmentService
from app.modules.organizations.invitations import OrganizationInvitationService, invitation_status
from app.modules.organizations.models import OrganizationInvitation
from app.modules.organizations.schemas import (
    InvitationAccept,
    InvitationAccepted,
    DepartmentCreate,
    DepartmentRead,
    DepartmentUpdate,
    MemberDepartmentUpdate,
    CourseAssignmentBulkCreate,
    CourseAssignmentList,
    CourseAssignmentRead,
    InvitationCreate,
    InvitationCreated,
    InvitationList,
    InvitationRead,
    MembershipRead,
    MembershipRoleUpdate,
    OrganizationCreate,
    OrganizationList,
    OrganizationLearningStats,
    OrganizationRead,
)
from app.modules.organizations.service import OrganizationService
from app.modules.users.models import User
from app.modules.users.rbac import RoleCode

router = APIRouter(prefix="/organizations", tags=["Organizations"])


def _invitation_read(invitation: OrganizationInvitation) -> InvitationRead:
    return InvitationRead(
        id=invitation.id,
        email=invitation.email_normalized,
        role=invitation.role,
        status=invitation_status(invitation),
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
        accepted_at=invitation.accepted_at,
        revoked_at=invitation.revoked_at,
    )


def _membership_read(row, *, can_update_role: bool = False, can_remove: bool = False) -> MembershipRead:
    membership, user = row
    return MembershipRead(
        id=membership.id,
        user_id=user.id,
        display_name=user.display_name,
        email=user.email,
        role=membership.role,
        status=membership.status,
        joined_at=membership.joined_at,
        created_at=membership.created_at,
        can_update_role=can_update_role,
        can_remove=can_remove,
        department_id=membership.department_id,
    )


def _member_action_flags(
    actor: User,
    actor_membership,
    target_membership,
    target_user: User,
    active_owner_count: int,
) -> tuple[bool, bool]:
    is_self = actor.id == target_user.id
    last_owner = target_membership.role == "owner" and active_owner_count <= 1
    platform_admin = OrganizationService.is_platform_admin(actor)

    if is_self or last_owner:
        return False, False
    if platform_admin or (actor_membership is not None and actor_membership.role == "owner"):
        return True, True
    if actor_membership is None:
        return False, False
    if actor_membership.role == "admin" and target_membership.role in {"manager", "employee"}:
        return True, True
    if (
        actor_membership.role == "manager"
        and target_membership.role == "employee"
        and not target_user.has_role(RoleCode.ADMIN)
    ):
        return False, True
    return False, False


def _assignment_read(row) -> CourseAssignmentRead:
    assignment, _membership, learner, course, enrollment, progress = row
    return CourseAssignmentRead(
        id=assignment.id,
        organization_id=assignment.organization_id,
        membership_id=assignment.membership_id,
        learner_user_id=learner.id,
        learner_name=learner.display_name,
        department_id=_membership.department_id,
        course_id=course.id,
        course_title=course.title,
        enrollment_id=assignment.enrollment_id,
        enrollment_status=enrollment.status if enrollment is not None else None,
        progress_percent=progress.progress_percent if progress is not None else None,
        is_course_completed=progress.is_completed if progress is not None else None,
        status=assignment.status,
        is_required=assignment.is_required,
        due_at=assignment.due_at,
        assigned_at=assignment.assigned_at,
        accepted_at=assignment.accepted_at,
        declined_at=assignment.declined_at,
        cancelled_at=assignment.cancelled_at,
        overdue_at=assignment.overdue_at,
    )


@router.post("", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
async def create_organization(payload: OrganizationCreate, user: CurrentUser, session: SessionDep):
    return await OrganizationService(session).create(user, name=payload.name, slug=payload.slug)


@router.get("/me", response_model=OrganizationList)
async def list_my_organizations(user: CurrentUser, session: SessionDep):
    return OrganizationList(items=await OrganizationService(session).list_for_user(user))


@router.get("/{organization_id}", response_model=OrganizationRead)
async def get_organization(organization_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    organization, _membership = await OrganizationService(session).get_authorized(user, organization_id)
    return organization


@router.get("/{organization_id}/members", response_model=list[MembershipRead])
async def list_members(organization_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    service = OrganizationService(session)
    rows = await service.list_members(user, organization_id)
    actor_membership = await service.get_membership(user.id, organization_id)
    owner_count = sum(1 for membership, _member in rows if membership.role == "owner")
    result = []
    for membership, member in rows:
        can_update_role, can_remove = _member_action_flags(
            user, actor_membership, membership, member, owner_count
        )
        result.append(_membership_read(
            (membership, member),
            can_update_role=can_update_role,
            can_remove=can_remove,
        ))
    return result


@router.patch("/{organization_id}/members/{membership_id}", response_model=MembershipRead)
async def update_member_role(
    organization_id: uuid.UUID,
    membership_id: uuid.UUID,
    payload: MembershipRoleUpdate,
    user: CurrentUser,
    session: SessionDep,
):
    membership = await OrganizationService(session).update_role(
        user, organization_id, membership_id, payload.role
    )
    from app.modules.users.models import User as UserModel

    member = await session.get(UserModel, membership.user_id)
    assert member is not None
    service = OrganizationService(session)
    rows = await service.list_members(user, organization_id)
    owner_count = sum(1 for row_membership, _row_user in rows if row_membership.role == "owner")
    actor_membership = await service.get_membership(user.id, organization_id)
    can_update_role, can_remove = _member_action_flags(
        user, actor_membership, membership, member, owner_count
    )
    return _membership_read(
        (membership, member),
        can_update_role=can_update_role,
        can_remove=can_remove,
    )


@router.delete("/{organization_id}/members/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(organization_id: uuid.UUID, membership_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    await OrganizationService(session).remove_member(user, organization_id, membership_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{organization_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_organization(organization_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    await OrganizationService(session).leave(user, organization_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _department_read(department, members_count: int = 0) -> DepartmentRead:
    return DepartmentRead(id=department.id, organization_id=department.organization_id,
                          name=department.name, slug=department.slug, members_count=members_count)


@router.get("/{organization_id}/departments", response_model=list[DepartmentRead])
async def list_departments(organization_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    rows = await OrganizationDepartmentService(session).list(user, organization_id)
    return [_department_read(department, count) for department, count in rows]


@router.post("/{organization_id}/departments", response_model=DepartmentRead, status_code=status.HTTP_201_CREATED)
async def create_department(organization_id: uuid.UUID, payload: DepartmentCreate, user: CurrentUser, session: SessionDep):
    department = await OrganizationDepartmentService(session).create(user, organization_id, payload.name)
    return _department_read(department)


@router.patch("/{organization_id}/departments/{department_id}", response_model=DepartmentRead)
async def rename_department(organization_id: uuid.UUID, department_id: uuid.UUID, payload: DepartmentUpdate, user: CurrentUser, session: SessionDep):
    department = await OrganizationDepartmentService(session).rename(user, organization_id, department_id, payload.name)
    return _department_read(department)


@router.delete("/{organization_id}/departments/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(organization_id: uuid.UUID, department_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    await OrganizationDepartmentService(session).delete(user, organization_id, department_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{organization_id}/members/{membership_id}/department", response_model=MembershipRead)
async def set_member_department(
    organization_id: uuid.UUID, membership_id: uuid.UUID, payload: MemberDepartmentUpdate,
    user: CurrentUser, session: SessionDep,
):
    membership = await OrganizationDepartmentService(session).set_member_department(
        user, organization_id, membership_id, payload.department_id
    )
    service = OrganizationService(session)
    rows = await service.list_members(user, organization_id)
    owner_count = sum(1 for item, _member in rows if item.role == "owner")
    member_user = next((item_user for item, item_user in rows if item.id == membership_id), None)
    if member_user is None:
        raise ApiError(404, "membership_not_found", "Active organization membership not found.")
    actor_membership = await service.get_membership(user.id, organization_id)
    can_update_role, can_remove = _member_action_flags(user, actor_membership, membership, member_user, owner_count)
    return _membership_read((membership, member_user), can_update_role=can_update_role, can_remove=can_remove)


@router.post("/invitations/accept", response_model=InvitationAccepted)
async def accept_invitation(payload: InvitationAccept, user: CurrentUser, session: SessionDep):
    invitation, membership = await OrganizationInvitationService(session).accept(user, token=payload.token)
    return InvitationAccepted(
        invitation_id=invitation.id,
        organization_id=invitation.organization_id,
        membership_id=membership.id,
        role=membership.role,
        joined_at=membership.joined_at,
    )


@router.post("/{organization_id}/invitations", response_model=InvitationCreated, status_code=status.HTTP_201_CREATED)
async def create_invitation(
    organization_id: uuid.UUID,
    payload: InvitationCreate,
    user: CurrentUser,
    session: SessionDep,
):
    invitation, token = await OrganizationInvitationService(session).create(
        user, organization_id, email=payload.email, role=payload.role
    )
    return InvitationCreated(
        id=invitation.id,
        email=invitation.email_normalized,
        role=invitation.role,
        status="pending",
        expires_at=invitation.expires_at,
        created_at=invitation.created_at,
        accepted_at=invitation.accepted_at,
        revoked_at=invitation.revoked_at,
        token=token,
    )


@router.get("/{organization_id}/invitations", response_model=InvitationList)
async def list_invitations(organization_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    invitations = await OrganizationInvitationService(session).list_for_organization(user, organization_id)
    return InvitationList(items=[_invitation_read(invitation) for invitation in invitations])


@router.delete("/{organization_id}/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_invitation(
    organization_id: uuid.UUID,
    invitation_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
):
    await OrganizationInvitationService(session).revoke(user, organization_id, invitation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{organization_id}/assignments", response_model=list[CourseAssignmentRead], status_code=status.HTTP_201_CREATED)
async def create_course_assignments(
    organization_id: uuid.UUID,
    payload: CourseAssignmentBulkCreate,
    user: CurrentUser,
    session: SessionDep,
):
    assignments = await OrganizationCourseAssignmentService(session).create_bulk(
        user, organization_id, course_id=payload.course_id,
        membership_ids=payload.membership_ids, due_at=payload.due_at,
        is_required=payload.is_required,
    )
    rows = await OrganizationCourseAssignmentService(session).list_for_organization(user, organization_id)
    by_id = {row[0].id: row for row in rows}
    return [_assignment_read(by_id[item.id]) for item in assignments if item.id in by_id]


@router.get("/{organization_id}/assignments", response_model=CourseAssignmentList)
async def list_course_assignments(organization_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    rows = await OrganizationCourseAssignmentService(session).list_for_organization(user, organization_id)
    return CourseAssignmentList(items=[_assignment_read(row) for row in rows], total=len(rows))


@router.get("/{organization_id}/learning-stats", response_model=OrganizationLearningStats)
async def organization_learning_stats(organization_id: uuid.UUID, user: CurrentUser, session: SessionDep):
    result = await OrganizationCourseAssignmentService(session).stats(user, organization_id)
    return OrganizationLearningStats(**result)


@router.post("/{organization_id}/assignments/{assignment_id}/accept", response_model=CourseAssignmentRead)
async def accept_course_assignment(
    organization_id: uuid.UUID, assignment_id: uuid.UUID, user: CurrentUser, session: SessionDep,
):
    assignment = await OrganizationCourseAssignmentService(session).respond(
        user, organization_id, assignment_id, accept=True
    )
    rows = await OrganizationCourseAssignmentService(session).list_for_organization(user, organization_id)
    row = next(item for item in rows if item[0].id == assignment.id)
    return _assignment_read(row)


@router.post("/{organization_id}/assignments/{assignment_id}/decline", response_model=CourseAssignmentRead)
async def decline_course_assignment(
    organization_id: uuid.UUID, assignment_id: uuid.UUID, user: CurrentUser, session: SessionDep,
):
    assignment = await OrganizationCourseAssignmentService(session).respond(
        user, organization_id, assignment_id, accept=False
    )
    rows = await OrganizationCourseAssignmentService(session).list_for_organization(user, organization_id)
    row = next(item for item in rows if item[0].id == assignment.id)
    return _assignment_read(row)


@router.delete("/{organization_id}/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_course_assignment(
    organization_id: uuid.UUID, assignment_id: uuid.UUID, user: CurrentUser, session: SessionDep,
):
    await OrganizationCourseAssignmentService(session).cancel(user, organization_id, assignment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
