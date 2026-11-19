"""Course vocabulary shared by ORM models, schemas and services.

Values are stored as plain strings (VARCHAR + CHECK constraints) rather than a
PostgreSQL ENUM type: adding a new level or status later is a data migration,
not a type rewrite. The same reason applies to roles in Sprint 1.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final


class CourseLevel(StrEnum):
    """Difficulty of a course."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class CourseStatus(StrEnum):
    """Lifecycle of a course.

    ``draft`` and ``archived`` are never visible in the public catalog;
    only ``published`` courses are.
    """

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


COURSE_STATUSES: Final[tuple[str, ...]] = tuple(status.value for status in CourseStatus)
COURSE_LEVELS: Final[tuple[str, ...]] = tuple(level.value for level in CourseLevel)

LEVEL_LABELS: Final[dict[str, str]] = {
    CourseLevel.BEGINNER.value: "Начальный",
    CourseLevel.INTERMEDIATE.value: "Средний",
    CourseLevel.ADVANCED.value: "Продвинутый",
}

STATUS_LABELS: Final[dict[str, str]] = {
    CourseStatus.DRAFT.value: "Черновик",
    CourseStatus.PUBLISHED.value: "Опубликован",
    CourseStatus.ARCHIVED.value: "В архиве",
}
