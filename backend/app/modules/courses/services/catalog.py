"""Public catalog queries: published courses and active categories only."""

from __future__ import annotations

import math

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.courses.models.category import Category
from app.modules.courses.repositories.category import CategoryRepository
from app.modules.courses.repositories.course import CourseRepository
from app.modules.courses.schemas.category import CategoryRead
from app.modules.courses.schemas.course import (
    CatalogCourseDetail,
    CatalogCourseRead,
    CatalogPage,
    catalog_course_from_orm,
    catalog_detail_from_orm,
)

MAX_PAGE_SIZE = 48


class CatalogService:
    def __init__(self, session: AsyncSession) -> None:
        self._courses = CourseRepository(session)
        self._categories = CategoryRepository(session)

    async def list_categories(self) -> list[CategoryRead]:
        categories: list[Category] = await self._categories.list_active()
        return [CategoryRead.model_validate(category) for category in categories]

    async def list_courses(
        self,
        *,
        search: str | None,
        category: str | None,
        level: str | None,
        language: str | None,
        sort: str,
        page: int,
        page_size: int,
    ) -> CatalogPage:
        normalized_search = search.strip() if search else None
        if normalized_search is not None and len(normalized_search) > 200:
            normalized_search = normalized_search[:200]

        offset = (page - 1) * page_size
        courses, total = await self._courses.list_public(
            search=normalized_search or None,
            category_slug=category,
            level=level,
            language=language,
            sort=sort,
            offset=offset,
            limit=page_size,
        )
        counts = await self._courses.counts_for_courses([course.id for course in courses])
        items: list[CatalogCourseRead] = [
            catalog_course_from_orm(
                course,
                modules_count=counts[course.id][0],
                lessons_count=counts[course.id][1],
                total_duration_minutes=counts[course.id][2],
            )
            for course in courses
        ]
        return CatalogPage(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=math.ceil(total / page_size) if total else 0,
        )

    async def get_course(self, slug: str) -> CatalogCourseDetail:
        course = await self._courses.get_public_by_slug(slug)
        if course is None:
            # Drafts, archived courses and inactive categories are all reported
            # as "not found": the public API must not reveal their existence.
            raise ApiError(404, "course_not_found", "Course not found.")
        return catalog_detail_from_orm(course)
