"""Course modules: ordered sections inside a course."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.modules.courses.models.course import Course


class CourseModule(Base):
    """A module belongs to exactly one course and is ordered by ``position``.

    Deletion is handled by the service inside a transaction: it removes the
    module, lets PostgreSQL cascade its lessons and renumbers the remaining
    modules so positions stay contiguous and unique.
    """

    __tablename__ = "course_modules"
    __table_args__ = (Index("ix_course_modules_course_id_position", "course_id", "position"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(2000), default=None)
    position: Mapped[int] = mapped_column(
        Integer,
        default=1,
        server_default=text("1"),
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

    course: Mapped[Course] = relationship(back_populates="modules")
    lessons: Mapped[list[Lesson]] = relationship(  # noqa: F821 - forward reference
        "Lesson",
        back_populates="module",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Lesson.position",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<CourseModule {self.id} position={self.position}>"
