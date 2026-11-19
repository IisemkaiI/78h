"""Public catalog endpoints (no authentication required).

Only published courses in active categories are reachable here. Drafts and
archived courses return 404 by slug, exactly like a non-existent course.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.api.deps import SessionDep
from app.modules.courses.constants import CourseLevel
from app.modules.courses.schemas.category import CategoryRead
from app.modules.courses.schemas.course import CatalogCourseDetail, CatalogPage
from app.modules.courses.services.catalog import MAX_PAGE_SIZE, CatalogService

router = APIRouter(prefix="/catalog", tags=["Catalog"])


@router.get(
    "/categories",
    response_model=list[CategoryRead],
    summary="List active categories",
    description="Returns active categories sorted by name. Inactive categories are hidden.",
)
async def list_categories(session: SessionDep) -> list[CategoryRead]:
    return await CatalogService(session).list_categories()


@router.get(
    "/courses",
    response_model=CatalogPage,
    summary="Browse the public course catalog",
    description=(
        "Lists published courses from active categories with case-insensitive "
        "search over the title and short description, plus category, level and "
        "language filters and offset pagination."
    ),
)
async def list_courses(
    session: SessionDep,
    search: Annotated[str | None, Query(max_length=200)] = None,
    category: Annotated[str | None, Query(max_length=140)] = None,
    level: CourseLevel | None = None,
    language: Annotated[str | None, Query(max_length=10)] = None,
    sort: Literal["newest", "oldest", "title"] = "newest",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 12,
) -> CatalogPage:
    return await CatalogService(session).list_courses(
        search=search,
        category=category,
        level=str(level) if level is not None else None,
        language=language.strip().lower() if language else None,
        sort=sort,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/courses/{slug}",
    response_model=CatalogCourseDetail,
    summary="Read a published course by slug",
    description=(
        "Returns the public course page with its module and lesson outline. "
        "Lesson content is intentionally omitted until enrollment exists (Sprint 4)."
    ),
    responses={404: {"description": "Course is not published or does not exist"}},
)
async def read_course(slug: str, session: SessionDep) -> CatalogCourseDetail:
    return await CatalogService(session).get_course(slug)
