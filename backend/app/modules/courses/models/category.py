"""Course categories: a flat taxonomy owned by the future admin module."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Category(Base):
    """A course category.

    Inactive categories stay in the database (their courses keep working) but
    are hidden from the public catalog and cannot receive new courses.
    """

    __tablename__ = "categories"
    __table_args__ = (Index("ix_categories_slug", "slug", unique=True),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(140), unique=True)
    description: Mapped[str | None] = mapped_column(String(500), default=None)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=text("true"),
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

    courses: Mapped[list[Course]] = relationship(  # noqa: F821 - forward reference
        "Course",
        back_populates="category",
        passive_deletes=True,
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Category {self.slug}>"
