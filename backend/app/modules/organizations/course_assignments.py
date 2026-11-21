"""Organization scoped course assignments and learning integration."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ApiError
from app.modules.courses.constants import CourseStatus
from app.modules.courses.models.course import Course
from app.modules.learning.models.enrollment import Enrollment
from app.modules.learning.services.enrollment import EnrollmentService
from app.modules.learning.services.progress import ProgressService
from app.modules.organizations.models import (
    Organization,
    OrganizationCourseAssignment,
    OrganizationMembership,
)
from app.modules.organizations.service import OrganizationService
from app.modules.users.models import User


class OrganizationCourseAssignmentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_bulk(
        self,
        actor: User,
        organization_id: uuid.UUID,
        *,
        course_id: uuid.UUID,
        membership_ids: list[uuid.UUID],
        due_at: datetime | None,
        is_required: bool,
    ) -> list[OrganizationCourseAssignment]:
        org, actor_member = await self._manager(actor, organization_id)
        if org.status != "active":
            raise ApiError(409, "organization_not_active", "Assignments require an active organization.")
        assert actor_member is not None
        if len(set(membership_ids)) != len(membership_ids):
            raise ApiError(422, "duplicate_membership_ids", "Each employee can appear only once in a bulk assignment.")
        course = await self.session.scalar(
            select(Course).where(Course.id == course_id).options(selectinload(Course.category)).with_for_update()
        )
        if course is None:
            raise ApiError(404, "course_not_found", "Course not found.")
        if course.status != CourseStatus.PUBLISHED.value or course.category is None or not course.category.is_active:
            raise ApiError(409, "course_not_available", "New assignments require a published course in an active category.")

        members = list((await self.session.scalars(select(OrganizationMembership).where(
            OrganizationMembership.organization_id == org.id,
            OrganizationMembership.id.in_(membership_ids),
            OrganizationMembership.status == "active",
        ).order_by(OrganizationMembership.id).with_for_update())).all())
        by_id = {member.id: member for member in members}
        if len(by_id) != len(membership_ids):
            raise ApiError(404, "membership_not_found", "One or more active organization memberships were not found.")
        if any(member.role != "employee" for member in members):
            raise ApiError(403, "assignment_target_forbidden", "Corporate courses can only be assigned to employees.")

        created: list[OrganizationCourseAssignment] = []
        now = datetime.now(UTC)
        try:
            for member in members:
                latest = await self.session.scalar(select(OrganizationCourseAssignment).where(
                    OrganizationCourseAssignment.organization_id == org.id,
                    OrganizationCourseAssignment.membership_id == member.id,
                    OrganizationCourseAssignment.course_id == course.id,
                ).order_by(OrganizationCourseAssignment.round_number.desc()).limit(1).with_for_update())
                if latest is not None and latest.status in {"pending", "accepted"}:
                    raise ApiError(409, "active_assignment_exists", "An active assignment for this employee and course already exists.")
                assignment = OrganizationCourseAssignment(
                    organization_id=org.id,
                    membership_id=member.id,
                    assigned_by_membership_id=actor_member.id,
                    course_id=course.id,
                    round_number=(latest.round_number + 1 if latest else 1),
                    status="pending",
                    is_required=is_required,
                    due_at=due_at,
                    assigned_at=now,
                )
                self.session.add(assignment)
                created.append(assignment)
            await self.session.flush()
            await self.session.commit()
        except ApiError:
            await self.session.rollback()
            raise
        except IntegrityError as exc:
            await self.session.rollback()
            raise ApiError(409, "active_assignment_exists", "An active assignment already exists.") from exc
        return created

    async def respond(self, actor: User, organization_id: uuid.UUID, assignment_id: uuid.UUID, *, accept: bool) -> OrganizationCourseAssignment:
        assigned_org_id = await self.session.scalar(select(OrganizationCourseAssignment.organization_id).where(
            OrganizationCourseAssignment.id == assignment_id
        ))
        if assigned_org_id is None or assigned_org_id != organization_id:
            raise ApiError(404, "assignment_not_found", "Corporate assignment not found.")
        # Writers lock the organization before its assignment rows to avoid
        # lock-order inversions with manager cancellation and bulk creation.
        org = await self.session.scalar(select(Organization).where(
            Organization.id == assigned_org_id
        ).with_for_update())
        assignment = await self.session.scalar(select(OrganizationCourseAssignment).where(
            OrganizationCourseAssignment.id == assignment_id,
            OrganizationCourseAssignment.organization_id == organization_id,
        ).with_for_update())
        if assignment is None:
            raise ApiError(404, "assignment_not_found", "Corporate assignment not found.")
        member = await self.session.scalar(select(OrganizationMembership).where(
            OrganizationMembership.id == assignment.membership_id,
            OrganizationMembership.organization_id == assignment.organization_id,
            OrganizationMembership.user_id == actor.id,
            OrganizationMembership.status == "active",
        ).with_for_update())
        if org is None or member is None or member.role != "employee":
            raise ApiError(404, "assignment_not_found", "Corporate assignment not found.")
        if assignment.status != "pending":
            raise ApiError(409, "assignment_not_pending", "Only pending assignments can be answered.")
        if accept:
            course = await self.session.scalar(select(Course).where(Course.id == assignment.course_id)
                .options(selectinload(Course.category), selectinload(Course.author)).with_for_update())
            if org.status != "active" or course is None or course.status != CourseStatus.PUBLISHED.value or course.category is None or not course.category.is_active:
                raise ApiError(409, "course_not_available", "The course is no longer available for new enrollment.")
            enrollment = await EnrollmentService(self.session).enroll_for_corporate_assignment(actor, course)
            assignment.enrollment_id = enrollment.id
            assignment.status = "accepted"
            assignment.accepted_at = datetime.now(UTC)
        else:
            assignment.status = "declined"
            assignment.declined_at = datetime.now(UTC)
        await self.session.commit()
        return assignment

    async def cancel(self, actor: User, organization_id: uuid.UUID, assignment_id: uuid.UUID) -> None:
        _org, _actor_member = await self._manager(actor, organization_id)
        assignment = await self.session.scalar(select(OrganizationCourseAssignment).where(
            OrganizationCourseAssignment.id == assignment_id,
            OrganizationCourseAssignment.organization_id == organization_id,
        ).with_for_update())
        if assignment is None:
            raise ApiError(404, "assignment_not_found", "Corporate assignment not found.")
        if assignment.status not in {"pending", "accepted"}:
            raise ApiError(409, "assignment_not_cancellable", "Only pending or accepted assignments can be cancelled.")
        assignment.status = "cancelled"
        assignment.cancelled_at = datetime.now(UTC)
        # A corporate assignment is independent from the learner's personal enrollment.
        await self.session.commit()

    async def list_for_organization(self, actor: User, organization_id: uuid.UUID) -> list[tuple]:
        org, actor_member = await OrganizationService(self.session).get_authorized(actor, organization_id)
        if actor_member is None:
            raise ApiError(404, "organization_not_found", "Organization not found.")
        statement = select(OrganizationCourseAssignment, OrganizationMembership, User, Course, Enrollment).join(
            OrganizationMembership, OrganizationMembership.id == OrganizationCourseAssignment.membership_id
        ).join(User, User.id == OrganizationMembership.user_id).join(
            Course, Course.id == OrganizationCourseAssignment.course_id
        ).outerjoin(Enrollment, Enrollment.id == OrganizationCourseAssignment.enrollment_id).where(
            OrganizationCourseAssignment.organization_id == org.id
        ).order_by(OrganizationCourseAssignment.assigned_at.desc(), OrganizationCourseAssignment.id)
        if actor_member.role == "employee":
            statement = statement.where(OrganizationCourseAssignment.membership_id == actor_member.id)
        rows = list((await self.session.execute(statement)).all())
        result: list[tuple] = []
        changed = False
        progress_service = ProgressService(self.session)
        for assignment, member, user, course, enrollment in rows:
            progress = None
            if enrollment is not None:
                progress, marker_changed = await progress_service.reconcile(enrollment)
                changed = changed or marker_changed
            result.append((assignment, member, user, course, enrollment, progress))
        if changed:
            await self.session.commit()
        return result

    async def stats(self, actor: User, organization_id: uuid.UUID) -> dict[str, int]:
        org, actor_member = await self._manager(actor, organization_id)
        assert actor_member is not None
        query = select(OrganizationCourseAssignment).where(
            OrganizationCourseAssignment.organization_id == org.id
        )
        assignments = list((await self.session.scalars(query)).all())
        counts = {state: sum(1 for row in assignments if row.status == state)
                  for state in ("pending", "accepted", "declined", "cancelled")}
        enrollment_ids = sorted({row.enrollment_id for row in assignments if row.enrollment_id is not None})
        enrollments = list((await self.session.scalars(select(Enrollment).where(
            Enrollment.id.in_(enrollment_ids)
        ))) .all()) if enrollment_ids else []
        progress_service = ProgressService(self.session)
        progress_values: list[int] = []
        changed = False
        for enrollment in enrollments:
            progress, marker_changed = await progress_service.reconcile(enrollment)
            progress_values.append(progress.progress_percent)
            changed = changed or marker_changed
        if changed:
            await self.session.commit()
        return {
            "assignments_total": len(assignments),
            "pending": counts["pending"], "accepted": counts["accepted"],
            "declined": counts["declined"], "cancelled": counts["cancelled"],
            "learners_total": len({row.membership_id for row in assignments}),
            "active_enrollments": sum(1 for row in enrollments if row.status == "active"),
            "completed_enrollments": sum(1 for row in enrollments if row.completed_at is not None),
            "average_progress_percent": round(sum(progress_values) / len(progress_values)) if progress_values else 0,
        }

    async def _manager(self, actor: User, organization_id: uuid.UUID) -> tuple[Organization, OrganizationMembership | None]:
        org, member = await OrganizationService(self.session)._lock_organization_and_authorize(
            actor, organization_id, "manage"
        )
        if member is None or member.role not in {"owner", "admin", "manager"}:
            raise ApiError(403, "organization_forbidden", "You cannot manage corporate course assignments.")
        return org, member
