"""Lesson request and response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

LESSON_TITLE_MIN_LENGTH = 2
LESSON_TITLE_MAX_LENGTH = 200
LESSON_DESCRIPTION_MAX_LENGTH = 2000
LESSON_CONTENT_MAX_LENGTH = 200_000
LESSON_DURATION_MAX_MINUTES = 10_000


def _clean_title(value: str) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) < LESSON_TITLE_MIN_LENGTH:
        raise ValueError(f"Title must be at least {LESSON_TITLE_MIN_LENGTH} characters.")
    if len(cleaned) > LESSON_TITLE_MAX_LENGTH:
        raise ValueError(f"Title must be at most {LESSON_TITLE_MAX_LENGTH} characters.")
    return cleaned


class LessonCreate(BaseModel):
    """A new lesson appended to a module."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=LESSON_TITLE_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=LESSON_DESCRIPTION_MAX_LENGTH)
    content: str = Field(default="", max_length=LESSON_CONTENT_MAX_LENGTH)
    estimated_duration_minutes: int = Field(default=0, ge=0, le=LESSON_DURATION_MAX_MINUTES)

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: str) -> str:
        return _clean_title(value)

    @field_validator("description")
    @classmethod
    def _validate_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class LessonUpdate(BaseModel):
    """Partial update of a lesson. Unknown fields are rejected."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=LESSON_TITLE_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=LESSON_DESCRIPTION_MAX_LENGTH)
    content: str | None = Field(default=None, max_length=LESSON_CONTENT_MAX_LENGTH)
    estimated_duration_minutes: int | None = Field(
        default=None,
        ge=0,
        le=LESSON_DURATION_MAX_MINUTES,
    )

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: str | None) -> str | None:
        return None if value is None else _clean_title(value)

    @field_validator("description")
    @classmethod
    def _validate_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class LessonRead(BaseModel):
    """Full lesson, including Markdown content (author view)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    module_id: uuid.UUID
    title: str
    description: str | None
    content: str
    position: int
    estimated_duration_minutes: int
    created_at: datetime
    updated_at: datetime


class LessonPreview(BaseModel):
    """Public lesson outline: no content until enrollment exists (Sprint 4)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    position: int
    estimated_duration_minutes: int
