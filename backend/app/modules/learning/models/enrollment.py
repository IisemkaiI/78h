"""Enrollment and append-only learning journal."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.modules.courses.models.course import Course
from app.modules.learning.constants import (
    ENROLLMENT_STATUSES,
    LEARNING_EVENT_TYPES,
    EnrollmentStatus,
)
from app.modules.users.models import User

_STATUS_SQL = ", ".join(f"'{value}'" for value in ENROLLMENT_STATUSES)
_EVENT_SQL = ", ".join(f"'{value}'" for value in LEARNING_EVENT_TYPES)


class Enrollment(Base):
    """One learner's relationship with one course.

    Exactly one row exists per ``(user_id, course_id)`` pair. Cancelling changes
    ``status``; re-enrolling reactivates the same row so progress and history
    survive. The completion marker is maintained from the current lesson
    structure by :class:`app.modules.learning.services.progress.ProgressService`.
    """

    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("user_id", "course_id"),
        Index("ix_enrollments_user_id", "user_id"),
        Index("ix_enrollments_course_id", "course_id"),
        Index("ix_enrollments_status", "status"),
        CheckConstraint(f"status IN ({_STATUS_SQL})", name="status_values"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=EnrollmentStatus.ACTIVE.value,
        server_default=text(f"'{EnrollmentStatus.ACTIVE.value}'"),
        nullable=False,
    )
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
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
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
    )
    last_activity_at: Mapped[datetime | None] = mapped_column(
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

    user: Mapped[User] = relationship(lazy="selectin")
    course: Mapped[Course] = relationship(lazy="selectin")
    progress_entries: Mapped[list[LessonProgress]] = relationship(  # noqa: F821
        "LessonProgress",
        back_populates="enrollment",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    events: Mapped[list[LearningEvent]] = relationship(
        back_populates="enrollment",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="LearningEvent.created_at",
    )

    @property
    def is_active(self) -> bool:
        return self.status == EnrollmentStatus.ACTIVE.value

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return (
            f"<Enrollment user={self.user_id} course={self.course_id} "
            f"status={self.status}>"
        )


class LearningEvent(Base):
    """Immutable journal row: what happened, when, and for which lesson."""

    __tablename__ = "learning_events"
    __table_args__ = (
        Index("ix_learning_events_enrollment_id_created_at", "enrollment_id", "created_at"),
        Index("ix_learning_events_lesson_id", "lesson_id"),
        CheckConstraint(f"event_type IN ({_EVENT_SQL})", name="event_type_values"),
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
    lesson_id_original: Mapped[uuid.UUID | None] = mapped_column(default=None)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )

    enrollment: Mapped[Enrollment] = relationship(back_populates="events")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<LearningEvent {self.event_type} enrollment={self.enrollment_id}>"
