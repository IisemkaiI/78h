"""User and RBAC ORM models.

Users can hold many roles, roles can hold many permissions — the classic
many-to-many RBAC model. A single Enum column on ``users`` is deliberately
avoided so that roles stay configurable and additive.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Table,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.database import Base
from app.core.security import normalize_email


class Role(Base):
    """A named set of permissions (guest, user, admin, ...)."""

    __tablename__ = "roles"
    __table_args__ = (Index("ix_roles_code", "code", unique=True),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(255), default=None)

    permissions: Mapped[list[Permission]] = relationship(
        secondary="role_permissions",
        back_populates="roles",
        lazy="selectin",
    )
    users: Mapped[list[User]] = relationship(
        secondary="user_roles",
        back_populates="roles",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Role {self.code}>"


class Permission(Base):
    """A single capability, e.g. ``users:read_self``."""

    __tablename__ = "permissions"
    __table_args__ = (Index("ix_permissions_code", "code", unique=True),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(String(255), default=None)

    roles: Mapped[list[Role]] = relationship(
        secondary="role_permissions",
        back_populates="permissions",
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Permission {self.code}>"


user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    """A registered platform account."""

    __tablename__ = "users"
    __table_args__ = (Index("ix_users_email", "email", unique=True),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(120))
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

    roles: Mapped[list[Role]] = relationship(
        secondary=user_roles,
        back_populates="users",
        lazy="selectin",
    )

    @validates("email")
    def _normalize_email(self, _key: str, value: str) -> str:
        """Guarantee normalisation regardless of the code path that writes."""
        return normalize_email(value)

    @property
    def role_codes(self) -> list[str]:
        return sorted(role.code for role in self.roles)

    @property
    def permission_codes(self) -> list[str]:
        """Union of permissions granted by every assigned role."""
        return sorted({permission.code for role in self.roles for permission in role.permissions})

    def has_role(self, *codes: str) -> bool:
        if not codes:
            return True
        assigned = {role.code for role in self.roles}
        return any(code in assigned for code in codes)

    def has_permissions(self, *codes: str) -> bool:
        if not codes:
            return True
        granted = set(self.permission_codes)
        return all(code in granted for code in codes)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<User {self.email}>"
