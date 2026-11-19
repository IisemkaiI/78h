"""Shared request/response helpers for the courses module."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class ReorderRequest(BaseModel):
    """New order for modules or lessons: every id, exactly once."""

    model_config = ConfigDict(extra="forbid")

    ids: list[uuid.UUID] = Field(
        min_length=1,
        description="All child ids in the desired order.",
    )
