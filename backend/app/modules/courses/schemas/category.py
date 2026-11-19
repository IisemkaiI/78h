"""Category schemas exposed by the public catalog."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CategoryRead(BaseModel):
    """An active category as shown in the public catalog."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str = Field(examples=["Программирование"])
    slug: str = Field(examples=["programming"])
    description: str | None = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class CategoryBrief(BaseModel):
    """Category embedded into a course payload."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
