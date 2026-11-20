"""Learning vocabulary shared by models, schemas and services."""

from __future__ import annotations

from enum import StrEnum
from typing import Final


class EnrollmentStatus(StrEnum):
    """Lifecycle of a learner's enrollment in one course."""

    ACTIVE = "active"
    CANCELLED = "cancelled"


class LessonState(StrEnum):
    """Three-state lesson progress.

    A missing ``lesson_progress`` row means ``not_started``; rows are created
    only when a learner actually interacts with a lesson.
    """

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class LearningEventType(StrEnum):
    """Append-only learning journal event types."""

    ENROLLED = "enrolled"
    CANCELLED = "cancelled"
    REACTIVATED = "reactivated"
    STARTED = "started"
    LESSON_STARTED = "lesson_started"
    LESSON_COMPLETED = "lesson_completed"
    LESSON_REOPENED = "lesson_reopened"
    LESSON_RESET = "lesson_reset"
    COURSE_COMPLETED = "course_completed"
    COURSE_REOPENED = "course_reopened"


ENROLLMENT_STATUSES: Final[tuple[str, ...]] = tuple(
    status.value for status in EnrollmentStatus
)
LESSON_STATES: Final[tuple[str, ...]] = tuple(state.value for state in LessonState)
LEARNING_EVENT_TYPES: Final[tuple[str, ...]] = tuple(
    event_type.value for event_type in LearningEventType
)
