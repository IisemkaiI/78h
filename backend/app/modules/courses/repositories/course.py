"""Persistence operations for courses.

Repositories contain SQL only; visibility rules and ownership checks live in
services. Every query that touches relationships eager-loads them, because
async SQLAlchemy cannot perform implicit lazy IO.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.courses.constants import CourseStatus
from app.modules.courses.models.category import Category
from app.modules.courses.models.course import Course
from app.modules.courses.models.lesson import Lesson
from app.modules.courses.models.module import CourseModule

PUBLIC_SORTS = ("newest", "oldest", "title")


class CourseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _with_author_and_category():
        return (
            selectinload(Course.author),
            selectinload(Course.category),
        )

    @classmethod
    def _with_structure(cls):
        return (
            *cls._with_author_and_category(),
            selectinload(Course.modules).selectinload(CourseModule.lessons),
        )

    async def get_by_id(self, course_id: uuid.UUID, *, with_structure: bool = True) -> Course | None:
        statement = select(Course).where(Course.id == course_id)
        options = self._with_structure() if with_structure else self._with_author_and_category()
        # Re-read from the database even if the object is already in the session:
        # services fetch a course again after committing changes.
        statement = statement.options(*options).execution_options(populate_existing=True)
        return await self._session.scalar(statement)

    async def get_public_by_slug(self, slug: str) -> Course | None:
        statement = (
            select(Course)
            .join(Category)
            .where(
                Course.slug == slug,
                Course.status == CourseStatus.PUBLISHED.value,
                Category.is_active.is_(True),
            )
            .options(*self._with_structure())
        )
        return await self._session.scalar(statement)

    async def slug_exists(self, slug: str) -> bool:
        statement = select(Course.id).where(Course.slug == slug).limit(1)
        return await self._session.scalar(statement) is not None

    async def add(
        self,
        *,
        title: str,
        slug: str,
        short_description: str,
        description: str,
        cover_image_url: str | None,
        level: str,
        language: str,
        author_id: uuid.UUID,
        category_id: uuid.UUID,
    ) -> Course:
        course = Course(
            title=title,
            slug=slug,
            short_description=short_description,
            description=description,
            cover_image_url=cover_image_url,
            level=level,
            language=language,
            status=CourseStatus.DRAFT.value,
            author_id=author_id,
            category_id=category_id,
            published_at=None,
        )
        self._session.add(course)
        await self._session.flush()
        return course

    async def delete(self, course: Course) -> None:
        await self._session.delete(course)
        await self._session.flush()

    async def list_for_author(
        self,
        author_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
    ) -> tuple[list[Course], int]:
        statement = (
            select(Course)
            .where(Course.author_id == author_id)
            .order_by(Course.updated_at.desc())
            .offset(offset)
            .limit(limit)
            .options(*self._with_author_and_category())
        )
        total = await self._session.scalar(
            select(func.count(Course.id)).where(Course.author_id == author_id)
        )
        return list(await self._session.scalars(statement)), int(total or 0)

    async def list_public(
        self,
        *,
        search: str | None,
        category_slug: str | None,
        level: str | None,
        language: str | None,
        sort: str,
        offset: int,
        limit: int,
    ) -> tuple[list[Course], int]:
        filters = [
            Course.status == CourseStatus.PUBLISHED.value,
            Category.is_active.is_(True),
        ]
        if search:
            pattern = f"%{search}%"
            filters.append(
                or_(
                    Course.title.ilike(pattern),
                    Course.short_description.ilike(pattern),
                )
            )
        if category_slug:
            filters.append(Category.slug == category_slug)
        if level:
            filters.append(Course.level == level)
        if language:
            filters.append(Course.language == language)

        statement = (
            select(Course)
            .join(Category)
            .where(*filters)
            .options(*self._with_author_and_category())
        )
        if sort == "title":
            statement = statement.order_by(Course.title.asc())
        elif sort == "oldest":
            statement = statement.order_by(Course.published_at.asc().nulls_last())
        else:
            statement = statement.order_by(Course.published_at.desc().nulls_last())

        statement = statement.offset(offset).limit(limit)
        total = await self._session.scalar(
            select(func.count(Course.id)).join(Category).where(*filters)
        )
        return list(await self._session.scalars(statement)), int(total or 0)

    async def counts_for_courses(
        self, course_ids: Sequence[uuid.UUID]
    ) -> dict[uuid.UUID, tuple[int, int, int]]:
        """Return ``{course_id: (modules, lessons, total_minutes)}``.

        One grouped query instead of per-row correlated subqueries.
        """
        result: dict[uuid.UUID, tuple[int, int, int]] = {
            course_id: (0, 0, 0) for course_id in course_ids
        }
        if not course_ids:
            return result

        statement = (
            select(
                CourseModule.course_id,
                func.count(func.distinct(CourseModule.id)),
                func.count(Lesson.id),
                func.coalesce(func.sum(Lesson.estimated_duration_minutes), 0),
            )
            .outerjoin(Lesson, Lesson.module_id == CourseModule.id)
            .where(CourseModule.course_id.in_(list(course_ids)))
            .group_by(CourseModule.course_id)
        )
        rows = await self._session.execute(statement)
        for course_id, modules_count, lessons_count, duration in rows:
            result[course_id] = (
                int(modules_count),
                int(lessons_count),
                int(duration),
            )
        return result
