"""Pydantic schemas for users and RBAC.

Requests use ``extra="forbid"`` so a client cannot smuggle fields such as
``roles`` or ``is_active`` into a registration or profile update payload.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.security import PASSWORD_MAX_LENGTH, normalize_email, validate_password_strength
from app.modules.users.models import User

DISPLAY_NAME_MIN_LENGTH = 2
DISPLAY_NAME_MAX_LENGTH = 120


class RoleRead(BaseModel):
    """Role as exposed to the client."""

    code: str = Field(examples=["course_author"])
    name: str = Field(examples=["Автор курсов"])


class UserRead(BaseModel):
    """Public representation of an account. Never contains the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    roles: list[RoleRead]
    permissions: list[str]

    @classmethod
    def from_user(cls, user: User) -> UserRead:
        return cls(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            is_active=user.is_active,
            created_at=user.created_at,
            updated_at=user.updated_at,
            roles=[RoleRead(code=role.code, name=role.name) for role in sorted(user.roles, key=lambda r: r.code)],
            permissions=user.permission_codes,
        )


def _validate_display_name(value: str) -> str:
    cleaned = " ".join(value.split())
    if len(cleaned) < DISPLAY_NAME_MIN_LENGTH:
        raise ValueError(f"Display name must be at least {DISPLAY_NAME_MIN_LENGTH} characters.")
    if len(cleaned) > DISPLAY_NAME_MAX_LENGTH:
        raise ValueError(f"Display name must be at most {DISPLAY_NAME_MAX_LENGTH} characters.")
    if not any(ch.isalnum() for ch in cleaned):
        raise ValueError("Display name must contain at least one letter or digit.")
    return cleaned


class RegisterRequest(BaseModel):
    """Public registration payload — only these three fields are accepted."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr = Field(description="Account email; normalised to lowercase.")
    password: str = Field(
        min_length=1,
        max_length=PASSWORD_MAX_LENGTH,
        description="At least 10 characters, must contain a letter and a digit.",
    )
    display_name: str = Field(
        min_length=DISPLAY_NAME_MIN_LENGTH,
        max_length=DISPLAY_NAME_MAX_LENGTH,
        description="Name shown in the UI.",
    )

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: EmailStr) -> str:
        return normalize_email(str(value))

    @field_validator("password")
    @classmethod
    def _check_password(cls, value: str) -> str:
        problems = validate_password_strength(value)
        if problems:
            raise ValueError(" ".join(problems))
        return value

    @field_validator("display_name")
    @classmethod
    def _check_display_name(cls, value: str) -> str:
        return _validate_display_name(value)


class LoginRequest(BaseModel):
    """Credentials for the password grant."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: EmailStr) -> str:
        return normalize_email(str(value))


class TokenResponse(BaseModel):
    """Issued access token plus the profile it belongs to."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Token lifetime in seconds.")
    user: UserRead


class UpdateProfileRequest(BaseModel):
    """Fields a user may change on their own profile."""

    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(
        min_length=DISPLAY_NAME_MIN_LENGTH,
        max_length=DISPLAY_NAME_MAX_LENGTH,
    )

    @field_validator("display_name")
    @classmethod
    def _check_display_name(cls, value: str) -> str:
        return _validate_display_name(value)
