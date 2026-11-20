"""Immutable course certificate issuance records."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.modules.learning.models.enrollment import Enrollment


class Certificate(Base):
    """A certificate snapshot issued once for a single enrollment."""

    __tablename__ = "certificates"
    __table_args__ = (Index("ix_certificates_issued_at", "issued_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enrollments.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    recipient_name: Mapped[str] = mapped_column(String(120), nullable=False)
    course_title: Mapped[str] = mapped_column(String(200), nullable=False)
    completion_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )
    certificate_number: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    verification_code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    template_version: Mapped[str] = mapped_column(
        String(20), default="1", server_default="1", nullable=False
    )
    pdf_storage_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )

    enrollment: Mapped[Enrollment] = relationship(lazy="selectin")
