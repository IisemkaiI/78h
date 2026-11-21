"""Enrollment lifecycle: enroll, cancel, reactivate, list and start."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.courses.constants import CourseLevel, CourseStatus
from app.modules.courses.models.course import Course
from app.modules.courses.repositories.course import CourseRepository
from app.modules.learning.constants import EnrollmentStatus, LearningEventType
from app.modules.learning.models.enrollment import Enrollment
from app.modules.learning.repositories.enrollment import (
    EnrollmentRepository,
    LearningEventRepository,
)
from app.modules.learning.schemas import (
    CourseProgressRead,
    EnrollmentCourseRead,
    EnrollmentPage,
    EnrollmentRead,
    EnrollmentStatusRead,
)
from app.modules.learning.services.access import (
    ensure_active_enrollment,
    ensure_enrollment_access,
    is_course_available,
    ensure_course_available_for_existing_enrollment,
)
from app.modules.learning.services.progress import ProgressService
from app.modules.users.models import User

MAX_PAGE_SIZE = 48


def _course_card(course: Course) -> EnrollmentCourseRead:
    return EnrollmentCourseRead(
        id=course.id,
        title=course.title,
        slug=course.slug,
        short_description=course.short_description,
        cover_image_url=course.cover_image_url,
        level=CourseLevel(course.level),
        language=course.language,
        category_name=course.category.name,
        author_display_name=course.author.display_name,
    )


def enrollment_read(
    enrollment: Enrollment, progress: CourseProgressRead
) -> EnrollmentRead:
    return EnrollmentRead(
        id=enrollment.id,
        user_id=enrollment.user_id,
        course_id=enrollment.course_id,
        status=EnrollmentStatus(enrollment.status),
        enrolled_at=enrollment.enrolled_at,
        started_at=enrollment.started_at,
        completed_at=enrollment.completed_at,
        cancelled_at=enrollment.cancelled_at,
        last_activity_at=enrollment.last_activity_at,
        created_at=enrollment.created_at,
        updated_at=enrollment.updated_at,
        course=_course_card(enrollment.course),
        progress=progress,
    )


class EnrollmentService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._enrollments = EnrollmentRepository(session)
        self._events = LearningEventRepository(session)
        self._courses = CourseRepository(session)
        self._progress = ProgressService(session)

    async def enroll_for_corporate_assignment(self, user: User, course: Course) -> Enrollment:
        """Create or reactivate an enrollment without committing its caller's transaction."""
        if not is_course_available(course):
            raise ApiError(409, "course_not_available", "New enrollment requires a published course.")
        if course.author_id == user.id:
            raise ApiError(403, "own_course_enrollment_forbidden", "The author cannot enroll in their own course.")
        # Serialise first-time enrollments for this learner so two assignments
        # from separate organizations cannot race on the unique user/course key.
        await self._session.scalar(select(User).where(User.id == user.id).with_for_update())
        enrollment = await self._enrollments.get_by_user_and_course(user.id, course.id, for_update=True)
        now = datetime.now(UTC)
        if enrollment is None:
            enrollment = await self._enrollments.add(user_id=user.id, course_id=course.id)
            enrollment.course = course
            enrollment.last_activity_at = now
            await self._events.add(
                enrollment_id=enrollment.id,
                event_type=LearningEventType.ENROLLED.value,
                payload={"course_id": str(course.id), "source": "corporate_assignment"},
            )
        elif not enrollment.is_active:
            enrollment.status = EnrollmentStatus.ACTIVE.value
            enrollment.cancelled_at = None
            enrollment.last_activity_at = now
            await self._events.add(
                enrollment_id=enrollment.id,
                event_type=LearningEventType.REACTIVATED.value,
                payload={"course_id": str(course.id), "source": "corporate_assignment"},
            )
        await self._progress.reconcile(enrollment)
        return enrollment

    async def enroll(
        self, user: User, course_id: uuid.UUID
    ) -> tuple[EnrollmentRead, bool]:
        """Enroll or reactivate. Returns ``(enrollment, created)``.

        ``created`` drives the HTTP status: 201 for a new row, 200 when an
        existing cancelled row is reactivated.
        """
        course = await self._courses.get_by_id(course_id, with_structure=False)
        if course is None:
            raise ApiError(404, "course_not_found", "Course not found.")
        if course.author_id == user.id:
            raise ApiError(
                403,
                "own_course_enrollment_forbidden",
                "The author cannot enroll in their own course.",
            )

        await self._session.scalar(select(User).where(User.id == user.id).with_for_update())
        existing = await self._enrollments.get_by_user_and_course(
            user.id, course.id, for_update=True
        )
        is_archived_reactivation = (
            existing is not None
            and not existing.is_active
            and course.status == CourseStatus.ARCHIVED.value
        )
        if not is_course_available(course) and not is_archived_reactivation:
            raise ApiError(404, "course_not_found", "Course not found.")
        now = datetime.now(UTC)
        created = existing is None

        try:
            if existing is not None:
                if existing.is_active:
                    raise ApiError(409, "already_enrolled", "You are already enrolled.")
                existing.status = EnrollmentStatus.ACTIVE.value
                existing.cancelled_at = None
                existing.last_activity_at = now
                enrollment = existing
                await self._events.add(
                    enrollment_id=enrollment.id,
                    event_type=LearningEventType.REACTIVATED.value,
                    payload={"course_id": str(course.id)},
                )
            else:
                enrollment = await self._enrollments.add(
                    user_id=user.id, course_id=course.id
                )
                enrollment.course = course
                enrollment.last_activity_at = now
                await self._events.add(
                    enrollment_id=enrollment.id,
                    event_type=LearningEventType.ENROLLED.value,
                    payload={"course_id": str(course.id)},
                )

            progress, _ = await self._progress.reconcile(enrollment)
            await self._session.commit()
        except IntegrityError as exc:
            # Two concurrent first-time requests: the unique (user, course)
            # constraint picks a winner; the loser gets the same 409 as a
            # sequential duplicate instead of a 500.
            await self._session.rollback()
            if "uq_enrollments_user_id_course_id" in str(exc.orig):
                raise ApiError(
                    409, "already_enrolled", "You are already enrolled."
                ) from exc
            raise

        return enrollment_read(enrollment, progress), created

    async def list_mine(self, user: User, *, page: int, page_size: int) -> EnrollmentPage:
        offset = (page - 1) * page_size
        enrollments, total = await self._enrollments.list_for_user(
            user.id, offset=offset, limit=page_size, for_update=True
        )
        items: list[EnrollmentRead] = []
        changed = False
        for enrollment in enrollments:
            progress, marker_changed = await self._progress.reconcile(enrollment)
            changed = changed or marker_changed
            items.append(enrollment_read(enrollment, progress))
        if changed:
            await self._session.commit()
        return EnrollmentPage(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=(total + page_size - 1) // page_size if total else 0,
        )

    async def list_all(self, *, page: int, page_size: int) -> EnrollmentPage:
        offset = (page - 1) * page_size
        enrollments, total = await self._enrollments.list_all(
            offset=offset, limit=page_size
        )
        items: list[EnrollmentRead] = []
        changed = False
        for enrollment in enrollments:
            progress, marker_changed = await self._progress.reconcile(enrollment)
            changed = changed or marker_changed
            items.append(enrollment_read(enrollment, progress))
        if changed:
            await self._session.commit()
        return EnrollmentPage(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=(total + page_size - 1) // page_size if total else 0,
        )

    async def get_detail(self, enrollment_id: uuid.UUID, user: User) -> EnrollmentRead:
        enrollment = await self._enrollments.get_by_id(enrollment_id, for_update=True)
        enrollment = ensure_enrollment_access(enrollment, user)
        assert enrollment is not None
        progress, changed = await self._progress.reconcile(enrollment)
        if changed:
            await self._session.commit()
        return enrollment_read(enrollment, progress)

    async def get_status(
        self, user: User, course_id: uuid.UUID
    ) -> EnrollmentStatusRead:
        enrollment = await self._enrollments.get_by_user_and_course(
            user.id, course_id, for_update=True
        )
        if enrollment is None:
            return EnrollmentStatusRead(enrolled=False, enrollment=None)
        progress, changed = await self._progress.reconcile(enrollment)
        if changed:
            await self._session.commit()
        return EnrollmentStatusRead(
            enrolled=enrollment.is_active,
            enrollment=enrollment_read(enrollment, progress),
        )

    async def cancel(self, enrollment_id: uuid.UUID, user: User) -> None:
        enrollment = await self._enrollments.get_by_id(enrollment_id, for_update=True)
        enrollment = ensure_enrollment_access(enrollment, user)
        assert enrollment is not None
        if not enrollment.is_active:
            raise ApiError(
                409,
                "enrollment_cancelled",
                "This enrollment has already been cancelled.",
            )
        now = datetime.now(UTC)
        enrollment.status = EnrollmentStatus.CANCELLED.value
        enrollment.cancelled_at = now
        enrollment.last_activity_at = now
        await self._events.add(
            enrollment_id=enrollment.id,
            event_type=LearningEventType.CANCELLED.value,
            payload={"course_id": str(enrollment.course_id)},
        )
        await self._session.commit()

    async def start(self, enrollment_id: uuid.UUID, user: User) -> EnrollmentRead:
        enrollment = await self._enrollments.get_by_id(enrollment_id, for_update=True)
        enrollment = ensure_active_enrollment(enrollment, user)
        assert enrollment is not None
        ensure_course_available_for_existing_enrollment(enrollment)
        if enrollment.started_at is None:
            enrollment.started_at = datetime.now(UTC)
            await self._events.add(
                enrollment_id=enrollment.id,
                event_type=LearningEventType.STARTED.value,
                payload={"course_id": str(enrollment.course_id)},
            )
        progress, _ = await self._progress.reconcile(enrollment)
        await self._session.commit()
        return enrollment_read(enrollment, progress)
