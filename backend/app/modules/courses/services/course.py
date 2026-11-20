"""Course lifecycle: creation, editing, publication, archiving and deletion.

All ownership checks go through :mod:`app.modules.courses.services.access`.
HTTP dependencies check the coarse permission; services check the concrete
record, so swapping a UUID in a URL can never touch someone else's course.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.courses.constants import COURSE_LEVELS, CourseStatus
from app.modules.courses.models.course import Course
from app.modules.courses.repositories.category import CategoryRepository
from app.modules.courses.repositories.course import CourseRepository
from app.modules.courses.schemas.course import (
    CourseCreate,
    CourseDetail,
    CourseSummary,
    CourseUpdate,
    course_detail_from_orm,
    course_summary_from_orm,
)
from app.modules.courses.services.access import ensure_course_access
from app.modules.courses.services.slug import unique_course_slug
from app.modules.learning.repositories.enrollment import EnrollmentRepository
from app.modules.users.models import User

logger = logging.getLogger(__name__)

MIN_TITLE_LENGTH = 3
MIN_SHORT_DESCRIPTION_LENGTH = 10
MIN_DESCRIPTION_LENGTH = 20


class CourseService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._courses = CourseRepository(session)
        self._categories = CategoryRepository(session)

    async def create(self, user: User, payload: CourseCreate) -> CourseDetail:
        category = await self._categories.get_by_id(payload.category_id)
        if category is None:
            raise ApiError(404, "category_not_found", "Category not found.")
        if not category.is_active:
            raise ApiError(
                422,
                "category_inactive",
                "Courses cannot be created in an inactive category.",
            )

        slug = await unique_course_slug(self._courses, payload.title)
        course = await self._courses.add(
            title=payload.title,
            slug=slug,
            short_description=payload.short_description,
            description=payload.description,
            cover_image_url=payload.cover_image_url,
            level=str(payload.level),
            language=payload.language,
            author_id=user.id,
            category_id=category.id,
        )
        await self._session.commit()
        logger.info("Created course %s by author %s", course.id, user.id)

        loaded = await self._courses.get_by_id(course.id)
        assert loaded is not None
        return course_detail_from_orm(loaded)

    async def list_mine(
        self, user: User, *, page: int, page_size: int
    ) -> tuple[list[CourseSummary], int]:
        offset = (page - 1) * page_size
        courses, total = await self._courses.list_for_author(
            user.id, offset=offset, limit=page_size
        )
        counts = await self._courses.counts_for_courses([course.id for course in courses])
        items = [
            course_summary_from_orm(
                course,
                modules_count=counts[course.id][0],
                lessons_count=counts[course.id][1],
                total_duration_minutes=counts[course.id][2],
            )
            for course in courses
        ]
        return items, total

    async def get_for_editor(self, course_id: uuid.UUID, user: User) -> Course:
        course = await self._courses.get_by_id(course_id)
        return ensure_course_access(course, user)

    async def update(
        self, course_id: uuid.UUID, user: User, payload: CourseUpdate
    ) -> CourseDetail:
        course = ensure_course_access(await self._courses.get_by_id(course_id), user)
        changes = payload.model_dump(exclude_unset=True)

        if "category_id" in changes and changes["category_id"] != course.category_id:
            category = await self._categories.get_by_id(changes["category_id"])
            if category is None:
                raise ApiError(404, "category_not_found", "Category not found.")
            if not category.is_active:
                raise ApiError(
                    422,
                    "category_inactive",
                    "An inactive category cannot receive new courses.",
                )
            course.category_id = category.id
            course.category = category

        for field in ("title", "short_description", "description", "cover_image_url", "language"):
            if field in changes:
                setattr(course, field, changes[field])
        if "level" in changes:
            course.level = str(changes["level"])

        await self._session.commit()
        logger.info("Updated course %s by user %s", course.id, user.id)

        loaded = await self._courses.get_by_id(course.id)
        assert loaded is not None
        return course_detail_from_orm(loaded)

    async def publish(self, course_id: uuid.UUID, user: User) -> CourseDetail:
        course = ensure_course_access(await self._courses.get_by_id(course_id), user)
        self._ensure_publishable(course)

        if course.status != CourseStatus.PUBLISHED.value:
            course.status = CourseStatus.PUBLISHED.value
        if course.published_at is None:
            # First publication only: re-publishing keeps the original date.
            course.published_at = datetime.now(UTC)

        await self._session.commit()
        logger.info("Published course %s by user %s", course.id, user.id)

        loaded = await self._courses.get_by_id(course.id)
        assert loaded is not None
        return course_detail_from_orm(loaded)

    async def unpublish(self, course_id: uuid.UUID, user: User) -> CourseDetail:
        course = ensure_course_access(await self._courses.get_by_id(course_id), user)
        if course.status != CourseStatus.DRAFT.value:
            course.status = CourseStatus.DRAFT.value
            await self._session.commit()
            logger.info("Moved course %s back to draft", course.id)

        loaded = await self._courses.get_by_id(course.id)
        assert loaded is not None
        return course_detail_from_orm(loaded)

    async def archive(self, course_id: uuid.UUID, user: User) -> CourseDetail:
        course = ensure_course_access(await self._courses.get_by_id(course_id), user)
        if course.status != CourseStatus.ARCHIVED.value:
            course.status = CourseStatus.ARCHIVED.value
            await self._session.commit()
            logger.info("Archived course %s", course.id)

        loaded = await self._courses.get_by_id(course.id)
        assert loaded is not None
        return course_detail_from_orm(loaded)

    async def delete(self, course_id: uuid.UUID, user: User) -> None:
        course = await self._courses.get_by_id(course_id, with_structure=False)
        ensure_course_access(course, user)
        assert course is not None
        conflict = ApiError(
            409,
            "course_has_enrollments",
            "A course with enrollments cannot be deleted. Archive it instead.",
        )
        if await EnrollmentRepository(self._session).exists_for_course(course.id):
            raise conflict
        try:
            await self._courses.delete(course)
            await self._session.commit()
        except IntegrityError as exc:
            # A learner enrolled between the check and the DELETE; the RESTRICT
            # foreign key is the final guard. Report the same conflict instead
            # of leaking a 500.
            await self._session.rollback()
            raise conflict from exc
        logger.info("Deleted course %s", course.id)

    @staticmethod
    def _ensure_publishable(course: Course) -> None:
        """Collect every gap at once so the author can fix them in one pass."""
        missing: list[str] = []

        if len(" ".join(course.title.split())) < MIN_TITLE_LENGTH:
            missing.append("title")
        if len(" ".join(course.short_description.split())) < MIN_SHORT_DESCRIPTION_LENGTH:
            missing.append("short_description")
        if len(course.description.strip()) < MIN_DESCRIPTION_LENGTH:
            missing.append("description")
        if course.category is None or not course.category.is_active:
            missing.append("active_category")
        if course.level not in COURSE_LEVELS:
            missing.append("level")
        if not course.language.strip():
            missing.append("language")

        modules = list(course.modules)
        if not modules:
            missing.append("modules")
        else:
            for module_index, module in enumerate(modules, start=1):
                if not module.title.strip():
                    missing.append(f"module_{module_index}_title")
                if not module.lessons:
                    missing.append(f"module_{module_index}_lessons")
                    continue
                for lesson_index, lesson in enumerate(module.lessons, start=1):
                    if not lesson.title.strip():
                        missing.append(
                            f"module_{module_index}_lesson_{lesson_index}_title"
                        )
                    if lesson.estimated_duration_minutes < 0:
                        missing.append(
                            f"module_{module_index}_lesson_{lesson_index}_duration"
                        )

        if missing:
            raise ApiError(
                422,
                "course_not_ready",
                "Course is not ready for publication.",
                details={"missing": missing},
            )
