"""Learner-facing course programme and protected lesson content."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.courses.constants import CourseLevel, CourseStatus
from app.modules.courses.models.course import Course
from app.modules.courses.models.lesson import Lesson
from app.modules.courses.repositories.course import CourseRepository
from app.modules.learning.constants import LessonState
from app.modules.learning.models.enrollment import Enrollment
from app.modules.learning.models.progress import LessonProgress
from app.modules.learning.repositories.enrollment import EnrollmentRepository
from app.modules.learning.repositories.progress import ProgressRepository
from app.modules.learning.schemas import (
    CourseProgressRead,
    LearningCourseInfo,
    LearningCourseRead,
    LearningLessonContentRead,
    LearningLessonRead,
    LearningModuleRead,
)
from app.modules.learning.services.access import (
    has_any_learning_admin_right,
    is_course_available,
)
from app.modules.learning.services.progress import ProgressService
from app.modules.learning.services.progress_calc import calculate_progress
from app.modules.users.models import User


class LearningService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._courses = CourseRepository(session)
        self._enrollments = EnrollmentRepository(session)
        self._progress_rows = ProgressRepository(session)
        self._progress = ProgressService(session)

    async def get_course(self, slug: str, user: User) -> LearningCourseRead:
        course, enrollment = await self._resolve(slug, user)
        rows: list[LessonProgress] = []
        if enrollment is not None:
            progress, changed = await self._progress.reconcile(enrollment)
            if changed:
                await self._session.commit()
            rows = await self._progress_rows.list_for_enrollment(enrollment.id)
        else:
            total = sum(len(module.lessons) for module in course.modules)
            snapshot = calculate_progress(
                total_lessons=total,
                completed_lessons=0,
                in_progress_lessons=0,
            )
            progress = CourseProgressRead(
                total_lessons=snapshot.total_lessons,
                completed_lessons=snapshot.completed_lessons,
                in_progress_lessons=snapshot.in_progress_lessons,
                not_started_lessons=snapshot.not_started_lessons,
                progress_percent=snapshot.progress_percent,
                is_completed=snapshot.is_completed,
                completed_at=None,
                removed_lessons_count=0,
            )

        by_lesson = {
            row.lesson_id: row for row in rows if row.lesson_id is not None
        }
        return LearningCourseRead(
            enrollment_id=enrollment.id if enrollment is not None else None,
            course=self._course_info(course),
            progress=progress,
            modules=[
                LearningModuleRead(
                    id=module.id,
                    title=module.title,
                    description=module.description,
                    position=module.position,
                    lessons=[
                        self._lesson_read(lesson, by_lesson.get(lesson.id))
                        for lesson in module.lessons
                    ],
                )
                for module in course.modules
            ],
        )

    async def get_lesson(
        self,
        slug: str,
        lesson_id: uuid.UUID,
        user: User,
    ) -> LearningLessonContentRead:
        course, enrollment = await self._resolve(slug, user)
        found: tuple[Lesson, LessonProgress | None] | None = None
        row: LessonProgress | None = None
        if enrollment is not None:
            row = await self._progress_row_for_lesson(enrollment.id, lesson_id)

        for module in course.modules:
            for lesson in module.lessons:
                if lesson.id == lesson_id:
                    found = (lesson, row)
                    break
        if found is None:
            raise ApiError(404, "lesson_not_found", "Lesson not found.")

        lesson, row = found
        item = self._lesson_read(lesson, row)
        return LearningLessonContentRead(
            **item.model_dump(),
            content=lesson.content,
        )

    async def _progress_row_for_lesson(
        self, enrollment_id: uuid.UUID, lesson_id: uuid.UUID
    ) -> LessonProgress | None:
        return await self._progress_rows.get_by_lesson(enrollment_id, lesson_id)

    async def _resolve(
        self, slug: str, user: User
    ) -> tuple[Course, Enrollment | None]:
        course = await self._courses.get_by_slug(slug)
        if course is None:
            raise ApiError(404, "course_not_found", "Course not found.")

        enrollment = await self._enrollments.get_by_user_and_course(
            user.id, course.id, for_update=True
        )
        if enrollment is None:
            if not is_course_available(course):
                raise ApiError(404, "course_not_found", "Course not found.")
            if has_any_learning_admin_right(user):
                return course, None
            raise ApiError(
                403,
                "enrollment_required",
                "An active enrollment is required to access lesson content.",
            )

        if not enrollment.is_active:
            if has_any_learning_admin_right(user):
                # Administrators keep read access even if they cancelled their
                # own learner enrollment.
                if not is_course_available(course):
                    raise ApiError(
                        409,
                        "course_not_available",
                        "The course is no longer available for learning.",
                    )
                return course, None
            raise ApiError(
                403,
                "enrollment_required",
                "An active enrollment is required to access lesson content.",
            )
        if not is_course_available(course):
            raise ApiError(
                409,
                "course_not_available",
                "The course is no longer available for learning.",
            )
        return course, enrollment

    @staticmethod
    def _course_info(course: Course) -> LearningCourseInfo:
        return LearningCourseInfo(
            id=course.id,
            title=course.title,
            slug=course.slug,
            status=CourseStatus(course.status),
            cover_image_url=course.cover_image_url,
            level=CourseLevel(course.level),
            category_name=course.category.name,
        )

    @staticmethod
    def _lesson_read(
        lesson: Lesson, row: LessonProgress | None
    ) -> LearningLessonRead:
        return LearningLessonRead(
            id=lesson.id,
            module_id=lesson.module_id,
            title=lesson.title,
            description=lesson.description,
            position=lesson.position,
            estimated_duration_minutes=lesson.estimated_duration_minutes,
            state=LessonState(row.state) if row is not None else LessonState.NOT_STARTED,
            started_at=row.started_at if row is not None else None,
            completed_at=row.completed_at if row is not None else None,
        )
