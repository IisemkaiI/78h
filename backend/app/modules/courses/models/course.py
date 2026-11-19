"""Course: the central authoring aggregate."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.modules.courses.constants import COURSE_LEVELS, COURSE_STATUSES, CourseLevel, CourseStatus
from app.modules.courses.models.category import Category
from app.modules.users.models import User

_STATUS_SQL = ", ".join(f"'{value}'" for value in COURSE_STATUSES)
_LEVEL_SQL = ", ".join(f"'{value}'" for value in COURSE_LEVELS)


class Course(Base):
    """A course authored by exactly one user and owned by one category."""

    __tablename__ = "courses"
    __table_args__ = (
        Index("ix_courses_slug", "slug", unique=True),
        Index("ix_courses_author_id", "author_id"),
        Index("ix_courses_category_id", "category_id"),
        Index("ix_courses_status_published_at", "status", "published_at"),
        CheckConstraint(f"status IN ({_STATUS_SQL})", name="status_values"),
        CheckConstraint(f"level IN ({_LEVEL_SQL})", name="level_values"),    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(220), unique=True)
    short_description: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    cover_image_url: Mapped[str | None] = mapped_column(String(500), default=None)
    level: Mapped[str] = mapped_column(
        String(20),
        default=CourseLevel.BEGINNER.value,
        server_default=text(f"'{CourseLevel.BEGINNER.value}'"),
        nullable=False,
    )
    language: Mapped[str] = mapped_column(
        String(10),
        default="ru",
        server_default=text("'ru'"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default=CourseStatus.DRAFT.value,
        server_default=text(f"'{CourseStatus.DRAFT.value}'"),
        nullable=False,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"),
        nullable=False,
    )
    published_at: Mapped[datetime | None] = mapped_column(
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

    author: Mapped[User] = relationship(lazy="selectin")
    category: Mapped[Category] = relationship(
        back_populates="courses",
        lazy="selectin",
    )
    modules: Mapped[list[CourseModule]] = relationship(  # noqa: F821 - forward reference
        "CourseModule",
        back_populates="course",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="CourseModule.position",
    )

    @property
    def is_published(self) -> bool:
        return self.status == CourseStatus.PUBLISHED.value

    @property
    def modules_count(self) -> int:
        return len(self.modules)

    @property
    def lessons_count(self) -> int:
        return sum(len(module.lessons) for module in self.modules)

    @property
    def total_duration_minutes(self) -> int:
        return sum(
            lesson.estimated_duration_minutes
            for module in self.modules
            for lesson in module.lessons
        )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Course {self.slug} ({self.status})>"
