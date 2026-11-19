"""Course module request and response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.courses.schemas.lesson import LessonPreview, LessonRead

MODULE_TITLE_MIN_LENGTH = 2
MODULE_TITLE_MAX_LENGTH = 200
MODULE_DESCRIPTION_MAX_LENGTH = 2000


def _clean_title(value: str) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) < MODULE_TITLE_MIN_LENGTH:
        raise ValueError(f"Title must be at least {MODULE_TITLE_MIN_LENGTH} characters.")
    if len(cleaned) > MODULE_TITLE_MAX_LENGTH:
        raise ValueError(f"Title must be at most {MODULE_TITLE_MAX_LENGTH} characters.")
    return cleaned


class ModuleCreate(BaseModel):
    """A new module appended to the end of a course."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=MODULE_TITLE_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=MODULE_DESCRIPTION_MAX_LENGTH)

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


class ModuleUpdate(BaseModel):
    """Rename a module or change its description."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=MODULE_TITLE_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=MODULE_DESCRIPTION_MAX_LENGTH)

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


class ModuleRead(BaseModel):
    """Author view of a module with its lessons."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID
    title: str
    description: str | None
    position: int
    lessons: list[LessonRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ModulePreview(BaseModel):
    """Public module outline."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    description: str | None
    position: int
    lessons: list[LessonPreview] = Field(default_factory=list)
