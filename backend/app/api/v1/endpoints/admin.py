"""Small platform administration API, restricted to platform administrators."""
from __future__ import annotations

import math
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from app.api.deps import SessionDep
from app.core.errors import ApiError
from app.modules.auth.dependencies import require_permissions
from app.modules.courses.models.course import Course
from app.modules.courses.services.course import CourseService
from app.modules.organizations.models import Organization, OrganizationCourseAssignment, OrganizationMembership
from app.modules.users.models import Role, User
from app.modules.users.rbac import PermissionCode

router = APIRouter(prefix="/admin", tags=["Administration"])
Admin = Annotated[User, Depends(require_permissions(PermissionCode.ADMIN_MANAGE_PLATFORM))]
_REPORT_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="admin-report")


class AdminUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    display_name: str
    is_active: bool
    roles: list[str]
    created_at: datetime


class AdminUserPage(BaseModel):
    items: list[AdminUserRead]
    total: int
    page: int
    pages: int


class AdminUserStatusUpdate(BaseModel):
    is_active: bool


class AdminCourseRead(BaseModel):
    id: uuid.UUID
    title: str
    slug: str
    status: str
    author_name: str
    created_at: datetime


class AdminCoursePage(BaseModel):
    items: list[AdminCourseRead]
    total: int
    page: int
    pages: int


class AdminOrganizationRead(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    status: str
    members_count: int
    created_at: datetime


class AdminOverview(BaseModel):
    users_total: int
    organizations_total: int
    courses_total: int
    assignments_total: int
    assignments_pending: int
    assignments_accepted: int
    completed_courses: int
    average_progress_percent: int


async def _parallel_report_rollup(rows: list[tuple[str, int]]) -> tuple[int, int]:
    """Small CPU-only parallel report example; DB sessions never cross threads."""
    loop = asyncio.get_running_loop()
    values = [value for _name, value in rows]
    total_value, row_count = await asyncio.gather(
        loop.run_in_executor(_REPORT_EXECUTOR, sum, values),
        loop.run_in_executor(_REPORT_EXECUTOR, len, values),
    )
    return int(total_value), int(row_count)


@router.get("/overview", response_model=AdminOverview)
async def get_admin_overview(user: Admin, session: SessionDep):
    users_total = await session.scalar(select(func.count()).select_from(User)) or 0
    organizations_total = await session.scalar(select(func.count()).select_from(Organization)) or 0
    courses_total = await session.scalar(select(func.count()).select_from(Course)) or 0
    assignments = list((await session.execute(select(
        OrganizationCourseAssignment.status, OrganizationCourseAssignment.enrollment_id
    ))).all())
    counts = {state: sum(1 for status_, _enrollment_id in assignments if status_ == state)
              for state in ("pending", "accepted")}
    enrollment_ids = [row.enrollment_id for row in assignments if row.enrollment_id]
    completed = 0
    progress_values: list[int] = []
    changed = False
    if enrollment_ids:
        from app.modules.learning.models.enrollment import Enrollment
        from app.modules.learning.services.progress import ProgressService

        enrollments = list((await session.scalars(select(Enrollment).where(Enrollment.id.in_(enrollment_ids)))).all())
        for enrollment in enrollments:
            progress, marker_changed = await ProgressService(session).reconcile(enrollment)
            changed = changed or marker_changed
            completed += int(progress.is_completed)
            progress_values.append(progress.progress_percent)
        if changed:
            await session.commit()
    # CPU-only rollup demonstrates bounded thread usage without sharing AsyncSession.
    total_progress, sample_count = await _parallel_report_rollup([(str(i), value) for i, value in enumerate(progress_values)])
    return AdminOverview(
        users_total=int(users_total), organizations_total=int(organizations_total), courses_total=int(courses_total),
        assignments_total=len(assignments), assignments_pending=counts["pending"],
        assignments_accepted=counts["accepted"], completed_courses=completed,
        average_progress_percent=round(total_progress / sample_count) if sample_count else 0,
    )


@router.get("/users", response_model=AdminUserPage)
async def list_admin_users(
    user: Admin, session: SessionDep, q: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100),
):
    query = select(User).order_by(User.created_at.desc(), User.id)
    count_query = select(func.count()).select_from(User)
    if q:
        search = f"%{q.strip()}%"
        query = query.where((User.email.ilike(search)) | (User.display_name.ilike(search)))
        count_query = count_query.where((User.email.ilike(search)) | (User.display_name.ilike(search)))
    total = int(await session.scalar(count_query) or 0)
    users = list((await session.scalars(query.offset((page - 1) * page_size).limit(page_size))).all())
    return AdminUserPage(items=[AdminUserRead(
        id=item.id, email=item.email, display_name=item.display_name, is_active=item.is_active,
        roles=item.role_codes, created_at=item.created_at,
    ) for item in users], total=total, page=page, pages=math.ceil(total / page_size) if total else 0)


@router.patch("/users/{user_id}", response_model=AdminUserRead)
async def set_user_active(user_id: uuid.UUID, payload: AdminUserStatusUpdate, user: Admin, session: SessionDep):
    try:
        parsed_id = uuid.UUID(str(user_id))
    except ValueError as exc:
        raise ApiError(404, "user_not_found", "User not found.") from exc
    target = await session.scalar(select(User).where(User.id == parsed_id).with_for_update())
    if target is None:
        raise ApiError(404, "user_not_found", "User not found.")
    if target.id == user.id and not payload.is_active:
        raise ApiError(409, "cannot_deactivate_self", "An administrator cannot deactivate their own account.")
    if not payload.is_active and target.has_role("admin"):
        admin_role = await session.scalar(select(Role).where(Role.code == "admin").with_for_update())
        _ = admin_role
        active_admins = await session.scalar(select(func.count()).select_from(User).where(
            User.is_active.is_(True), User.roles.any(Role.code == "admin")
        )) or 0
        if active_admins <= 1:
            raise ApiError(409, "last_platform_admin_required", "At least one active platform administrator must remain.")
    target.is_active = payload.is_active
    await session.commit()
    await session.refresh(target)
    return AdminUserRead(id=target.id, email=target.email, display_name=target.display_name,
                         is_active=target.is_active, roles=target.role_codes, created_at=target.created_at)


@router.get("/courses", response_model=AdminCoursePage)
async def list_admin_courses(
    user: Admin, session: SessionDep, q: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1), page_size: int = Query(default=25, ge=1, le=100),
):
    query = select(Course, User).join(User, User.id == Course.author_id).order_by(Course.created_at.desc(), Course.id)
    count_query = select(func.count()).select_from(Course)
    if q:
        search = f"%{q.strip()}%"
        query = query.where(Course.title.ilike(search) | Course.slug.ilike(search))
        count_query = count_query.where(Course.title.ilike(search) | Course.slug.ilike(search))
    total = int(await session.scalar(count_query) or 0)
    rows = list((await session.execute(query.offset((page - 1) * page_size).limit(page_size))).all())
    return AdminCoursePage(items=[AdminCourseRead(id=course.id, title=course.title, slug=course.slug,
        status=course.status, author_name=author.display_name, created_at=course.created_at)
        for course, author in rows], total=total, page=page, pages=math.ceil(total / page_size) if total else 0)


@router.post("/courses/{course_id}/archive", status_code=status.HTTP_204_NO_CONTENT)
async def archive_admin_course(course_id: uuid.UUID, user: Admin, session: SessionDep):
    try:
        parsed_id = uuid.UUID(str(course_id))
    except ValueError as exc:
        raise ApiError(404, "course_not_found", "Course not found.") from exc
    await CourseService(session).archive(parsed_id, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/organizations", response_model=list[AdminOrganizationRead])
async def list_admin_organizations(user: Admin, session: SessionDep):
    rows = await session.execute(select(Organization, func.count(OrganizationMembership.id)).outerjoin(
        OrganizationMembership, (OrganizationMembership.organization_id == Organization.id)
        & (OrganizationMembership.status == "active")
    ).group_by(Organization.id).order_by(Organization.created_at.desc()))
    result = []
    for organization, members in rows.all():
        result.append(AdminOrganizationRead(id=organization.id, name=organization.name, slug=organization.slug,
            status=organization.status, members_count=int(members), created_at=organization.created_at))
    return result
