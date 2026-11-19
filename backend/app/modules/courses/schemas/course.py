"""Course request/response schemas and ORM → schema builders."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.courses.constants import CourseLevel, CourseStatus
from app.modules.courses.models.course import Course
from app.modules.courses.schemas.category import CategoryBrief
from app.modules.courses.schemas.module import ModulePreview, ModuleRead

COURSE_TITLE_MIN_LENGTH = 3
COURSE_TITLE_MAX_LENGTH = 200
COURSE_SHORT_DESCRIPTION_MIN_LENGTH = 10
COURSE_SHORT_DESCRIPTION_MAX_LENGTH = 300
COURSE_DESCRIPTION_MIN_LENGTH = 20
COURSE_DESCRIPTION_MAX_LENGTH = 20_000
COURSE_COVER_URL_MAX_LENGTH = 500

_LANGUAGE_PATTERN = re.compile(r"^[a-z]{2}(-[a-z]{2,4})?$")


def _clean_text(value: str, *, minimum: int, maximum: int, field: str) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) < minimum:
        raise ValueError(f"{field} must be at least {minimum} characters.")
    if len(cleaned) > maximum:
        raise ValueError(f"{field} must be at most {maximum} characters.")
    return cleaned


def _clean_long_text(value: str, *, minimum: int, maximum: int, field: str) -> str:
    cleaned = value.strip()
    if len(cleaned) < minimum:
        raise ValueError(f"{field} must be at least {minimum} characters.")
    if len(cleaned) > maximum:
        raise ValueError(f"{field} must be at most {maximum} characters.")
    return cleaned


def _validate_language(value: str) -> str:
    cleaned = value.strip().lower()
    if not _LANGUAGE_PATTERN.match(cleaned):
        raise ValueError("Language must be an ISO code such as 'ru' or 'en'.")
    return cleaned


def _validate_cover_url(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > COURSE_COVER_URL_MAX_LENGTH:
        raise ValueError(f"Cover URL must be at most {COURSE_COVER_URL_MAX_LENGTH} characters.")
    parsed = urlparse(cleaned)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Cover URL must be an absolute http(s) URL.")
    return cleaned


class AuthorRead(BaseModel):
    """Public author information attached to a course."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    display_name: str


class CourseCreate(BaseModel):
    """Fields accepted when an author creates a course.

    ``author_id``, ``status``, ``slug`` and ``published_at`` are never accepted
    from the client: the first three are derived by the server.
    """

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=COURSE_TITLE_MAX_LENGTH)
    short_description: str = Field(
        min_length=1,
        max_length=COURSE_SHORT_DESCRIPTION_MAX_LENGTH,
    )
    description: str = Field(min_length=1, max_length=COURSE_DESCRIPTION_MAX_LENGTH)
    cover_image_url: str | None = Field(default=None, max_length=COURSE_COVER_URL_MAX_LENGTH)
    level: CourseLevel = CourseLevel.BEGINNER
    language: str = Field(default="ru", max_length=10)
    category_id: uuid.UUID

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: str) -> str:
        return _clean_text(
            value,
            minimum=COURSE_TITLE_MIN_LENGTH,
            maximum=COURSE_TITLE_MAX_LENGTH,
            field="Title",
        )

    @field_validator("short_description")
    @classmethod
    def _validate_short_description(cls, value: str) -> str:
        return _clean_text(
            value,
            minimum=COURSE_SHORT_DESCRIPTION_MIN_LENGTH,
            maximum=COURSE_SHORT_DESCRIPTION_MAX_LENGTH,
            field="Short description",
        )

    @field_validator("description")
    @classmethod
    def _validate_description(cls, value: str) -> str:
        return _clean_long_text(
            value,
            minimum=COURSE_DESCRIPTION_MIN_LENGTH,
            maximum=COURSE_DESCRIPTION_MAX_LENGTH,
            field="Description",
        )

    @field_validator("cover_image_url")
    @classmethod
    def _validate_cover(cls, value: str | None) -> str | None:
        return _validate_cover_url(value)

    @field_validator("language")
    @classmethod
    def _validate_language(cls, value: str) -> str:
        return _validate_language(value)


class CourseUpdate(BaseModel):
    """Partial update of a course.

    The slug is intentionally immutable: changing it would break public links
    already shared for a published course.
    """

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=COURSE_TITLE_MAX_LENGTH)
    short_description: str | None = Field(
        default=None,
        max_length=COURSE_SHORT_DESCRIPTION_MAX_LENGTH,
    )
    description: str | None = Field(default=None, max_length=COURSE_DESCRIPTION_MAX_LENGTH)
    cover_image_url: str | None = Field(default=None, max_length=COURSE_COVER_URL_MAX_LENGTH)
    level: CourseLevel | None = None
    language: str | None = Field(default=None, max_length=10)
    category_id: uuid.UUID | None = None

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_text(
            value,
            minimum=COURSE_TITLE_MIN_LENGTH,
            maximum=COURSE_TITLE_MAX_LENGTH,
            field="Title",
        )

    @field_validator("short_description")
    @classmethod
    def _validate_short_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_text(
            value,
            minimum=COURSE_SHORT_DESCRIPTION_MIN_LENGTH,
            maximum=COURSE_SHORT_DESCRIPTION_MAX_LENGTH,
            field="Short description",
        )

    @field_validator("description")
    @classmethod
    def _validate_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _clean_long_text(
            value,
            minimum=COURSE_DESCRIPTION_MIN_LENGTH,
            maximum=COURSE_DESCRIPTION_MAX_LENGTH,
            field="Description",
        )

    @field_validator("cover_image_url")
    @classmethod
    def _validate_cover(cls, value: str | None) -> str | None:
        return _validate_cover_url(value)

    @field_validator("language")
    @classmethod
    def _validate_language(cls, value: str | None) -> str | None:
        return None if value is None else _validate_language(value)


class CourseSummary(BaseModel):
    """Course row for author dashboards (includes counts, no structure)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    slug: str
    short_description: str
    cover_image_url: str | None = None
    level: CourseLevel
    language: str
    status: CourseStatus
    author_id: uuid.UUID
    category: CategoryBrief
    author: AuthorRead
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    modules_count: int = 0
    lessons_count: int = 0
    total_duration_minutes: int = 0


class CourseDetail(CourseSummary):
    """Full author view of a course, including modules and lessons."""

    description: str
    modules: list[ModuleRead] = Field(default_factory=list)


class CatalogCourseRead(BaseModel):
    """Published course card in the public catalog."""

    id: uuid.UUID
    title: str
    slug: str
    short_description: str
    cover_image_url: str | None = None
    level: CourseLevel
    language: str
    category: CategoryBrief
    author: AuthorRead
    published_at: datetime | None = None
    modules_count: int = 0
    lessons_count: int = 0
    total_duration_minutes: int = 0


class CatalogCourseDetail(BaseModel):
    """Published course page: description plus the module/lesson outline."""

    id: uuid.UUID
    title: str
    slug: str
    short_description: str
    description: str
    cover_image_url: str | None = None
    level: CourseLevel
    language: str
    category: CategoryBrief
    author: AuthorRead
    published_at: datetime | None = None
    modules: list[ModulePreview] = Field(default_factory=list)
    modules_count: int = 0
    lessons_count: int = 0
    total_duration_minutes: int = 0


class CoursePage(BaseModel):
    """Paginated list of author courses."""

    items: list[CourseSummary]
    total: int
    page: int
    page_size: int
    pages: int


class CatalogPage(BaseModel):
    """Paginated public catalog response."""

    items: list[CatalogCourseRead]
    total: int
    page: int
    page_size: int
    pages: int


def _summary_fields(course: Course) -> dict:
    """Scalar fields plus loaded relationships, as a mapping.

    Pydantic's ``from_attributes`` would read the ``modules_count`` property,
    which triggers a lazy load on an async session. Building an explicit mapping
    keeps the query count predictable.
    """
    return {
        "id": course.id,
        "title": course.title,
        "slug": course.slug,
        "short_description": course.short_description,
        "cover_image_url": course.cover_image_url,
        "level": course.level,
        "language": course.language,
        "status": course.status,
        "author_id": course.author_id,
        "category": course.category,
        "author": course.author,
        "published_at": course.published_at,
        "created_at": course.created_at,
        "updated_at": course.updated_at,
    }


def course_summary_from_orm(
    course: Course,
    *,
    modules_count: int,
    lessons_count: int,
    total_duration_minutes: int,
) -> CourseSummary:
    """Build a summary without triggering lazy loads."""
    return CourseSummary.model_validate(
        {
            **_summary_fields(course),
            "modules_count": modules_count,
            "lessons_count": lessons_count,
            "total_duration_minutes": total_duration_minutes,
        }
    )


def course_detail_from_orm(course: Course) -> CourseDetail:
    """Build the author detail; ``course.modules[].lessons`` must be loaded."""
    modules = list(course.modules)
    lessons_count = sum(len(module.lessons) for module in modules)
    total_duration = sum(
        lesson.estimated_duration_minutes
        for module in modules
        for lesson in module.lessons
    )
    return CourseDetail.model_validate(
        {
            **_summary_fields(course),
            "description": course.description,
            "modules": modules,
            "modules_count": len(modules),
            "lessons_count": lessons_count,
            "total_duration_minutes": total_duration,
        }
    )


def catalog_course_from_orm(
    course: Course,
    *,
    modules_count: int,
    lessons_count: int,
    total_duration_minutes: int,
) -> CatalogCourseRead:
    base = CatalogCourseRead.model_validate(
        {
            "id": course.id,
            "title": course.title,
            "slug": course.slug,
            "short_description": course.short_description,
            "cover_image_url": course.cover_image_url,
            "level": course.level,
            "language": course.language,
            "category": course.category,
            "author": course.author,
            "published_at": course.published_at,
        }
    )
    return base.model_copy(
        update={
            "modules_count": modules_count,
            "lessons_count": lessons_count,
            "total_duration_minutes": total_duration_minutes,
        }
    )


def catalog_detail_from_orm(course: Course) -> CatalogCourseDetail:
    modules = list(course.modules)
    return CatalogCourseDetail.model_validate(
        {
            "id": course.id,
            "title": course.title,
            "slug": course.slug,
            "short_description": course.short_description,
            "description": course.description,
            "cover_image_url": course.cover_image_url,
            "level": course.level,
            "language": course.language,
            "category": course.category,
            "author": course.author,
            "published_at": course.published_at,
            "modules": modules,
            "modules_count": len(modules),
            "lessons_count": sum(len(module.lessons) for module in modules),
            "total_duration_minutes": sum(
                lesson.estimated_duration_minutes
                for module in modules
                for lesson in module.lessons
            ),
        }
    )
