"""Per-lesson progress with history-preserving snapshots."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.modules.learning.constants import LESSON_STATES, LessonState
from app.modules.learning.models.enrollment import Enrollment

_STATE_SQL = ", ".join(f"'{value}'" for value in LESSON_STATES)


class LessonProgress(Base):
    """Progress for one lesson inside one enrollment.

    When the author deletes a lesson, PostgreSQL nulls ``lesson_id`` but keeps
    this row: ``lesson_id_original``, titles and timestamps preserve the learning
    history. Current progress only counts rows whose ``lesson_id`` still exists;
    the snapshot rows are shown separately in the history.
    """

    __tablename__ = "lesson_progress"
    __table_args__ = (
        UniqueConstraint("enrollment_id", "lesson_id_original"),
        Index("ix_lesson_progress_enrollment_id_state", "enrollment_id", "state"),
        Index("ix_lesson_progress_lesson_id", "lesson_id"),
        Index("ix_lesson_progress_lesson_id_original", "lesson_id_original"),
        CheckConstraint(f"state IN ({_STATE_SQL})", name="state_values"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enrollments.id", ondelete="CASCADE"),
        nullable=False,
    )
    lesson_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("lessons.id", ondelete="SET NULL"),
        default=None,
    )
    lesson_id_original: Mapped[uuid.UUID] = mapped_column(nullable=False)
    module_id_original: Mapped[uuid.UUID] = mapped_column(nullable=False)
    lesson_title_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    module_title_snapshot: Mapped[str] = mapped_column(String(200), nullable=False)
    state: Mapped[str] = mapped_column(
        String(20),
        default=LessonState.NOT_STARTED.value,
        server_default=text(f"'{LessonState.NOT_STARTED.value}'"),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
    )
    last_viewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
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

    enrollment: Mapped[Enrollment] = relationship(back_populates="progress_entries")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<LessonProgress enrollment={self.enrollment_id} "
            f"lesson={self.lesson_id_original} state={self.state}>"
        )
