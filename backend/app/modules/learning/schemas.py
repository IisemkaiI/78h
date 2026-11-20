"""Request/response contracts for the learning module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.courses.constants import CourseLevel, CourseStatus
from app.modules.learning.constants import EnrollmentStatus, LessonState

# --- enrollment ----------------------------------------------------------


class EnrollmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    course_id: uuid.UUID


class EnrollmentCourseRead(BaseModel):
    """Compact course card attached to an enrollment."""

    id: uuid.UUID
    title: str
    slug: str
    short_description: str
    cover_image_url: str | None = None
    level: CourseLevel
    language: str
    category_name: str
    author_display_name: str


class CourseProgressRead(BaseModel):
    total_lessons: int
    completed_lessons: int
    in_progress_lessons: int
    not_started_lessons: int
    progress_percent: int
    is_completed: bool
    completed_at: datetime | None = None
    removed_lessons_count: int = 0


class EnrollmentRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    course_id: uuid.UUID
    status: EnrollmentStatus
    enrolled_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    last_activity_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    course: EnrollmentCourseRead
    progress: CourseProgressRead


class EnrollmentPage(BaseModel):
    items: list[EnrollmentRead]
    total: int
    page: int
    page_size: int
    pages: int


class EnrollmentStatusRead(BaseModel):
    """Enrollment state for one course, safe to call when not enrolled."""

    enrolled: bool
    enrollment: EnrollmentRead | None = None


# --- lesson progress -----------------------------------------------------


class LessonStateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: LessonState


class LessonProgressRead(BaseModel):
    lesson_id: uuid.UUID
    state: LessonState
    started_at: datetime | None = None
    completed_at: datetime | None = None
    last_viewed_at: datetime | None = None


class LessonProgressUpdateResult(BaseModel):
    lesson: LessonProgressRead
    course_progress: CourseProgressRead


class LearningEventRead(BaseModel):
    id: uuid.UUID
    event_type: str
    lesson_id: uuid.UUID | None = None
    lesson_id_original: uuid.UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class RemovedLessonRead(BaseModel):
    lesson_id_original: uuid.UUID
    module_id_original: uuid.UUID
    lesson_title: str
    module_title: str
    state: LessonState
    started_at: datetime | None = None
    completed_at: datetime | None = None


class LearningHistoryRead(BaseModel):
    events: list[LearningEventRead]
    removed_lessons: list[RemovedLessonRead]


# --- learning course -----------------------------------------------------


class LearningCourseInfo(BaseModel):
    id: uuid.UUID
    title: str
    slug: str
    status: CourseStatus
    cover_image_url: str | None = None
    level: CourseLevel
    category_name: str


class LearningLessonRead(BaseModel):
    id: uuid.UUID
    module_id: uuid.UUID
    title: str
    description: str | None
    position: int
    estimated_duration_minutes: int
    state: LessonState
    started_at: datetime | None = None
    completed_at: datetime | None = None


class LearningLessonContentRead(LearningLessonRead):
    content: str


class LearningModuleRead(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    position: int
    lessons: list[LearningLessonRead] = Field(default_factory=list)


class LearningCourseRead(BaseModel):
    enrollment_id: uuid.UUID | None = None
    course: LearningCourseInfo
    progress: CourseProgressRead
    modules: list[LearningModuleRead] = Field(default_factory=list)
