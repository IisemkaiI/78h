"""Lessons: ordered content units inside a course module."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.modules.courses.models.module import CourseModule


class Lesson(Base):
    """A lesson with Markdown content.

    Rich media (video, attachments, interactive blocks) is deliberately out of
    scope for Sprint 2: ``content`` is a Markdown text column that the client
    renders with a Markdown renderer.
    """

    __tablename__ = "lessons"
    __table_args__ = (
        Index("ix_lessons_module_id_position", "module_id", "position"),
        CheckConstraint(
            "estimated_duration_minutes >= 0",
            name="estimated_duration_minutes_non_negative",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    module_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course_modules.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(2000), default=None)
    content: Mapped[str] = mapped_column(
        Text,
        default="",
        server_default=text("''"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(
        Integer,
        default=1,
        server_default=text("1"),
        nullable=False,
    )
    estimated_duration_minutes: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default=text("0"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    module: Mapped[CourseModule] = relationship(back_populates="lessons")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Lesson {self.id} position={self.position}>"
