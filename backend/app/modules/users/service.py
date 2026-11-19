"""User business logic: registration, profile updates, RBAC assignment."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.core.security import hash_password, normalize_email, validate_password_strength
from app.modules.users.models import User
from app.modules.users.rbac import RoleCode
from app.modules.users.repository import UserRepository

logger = logging.getLogger(__name__)


def _duplicate_email_error() -> ApiError:
    return ApiError(
        409,
        "email_already_registered",
        "An account with this email already exists.",
    )


class UserService:
    """Application service for accounts."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)

    async def register(self, *, email: str, password: str, display_name: str) -> User:
        """Create an account with the base ``user`` role.

        Privileged roles are assigned only by administrators through internal
        tooling — never by this method.
        """
        normalized_email = normalize_email(email)

        problems = validate_password_strength(password, email=normalized_email)
        if problems:
            raise ApiError(
                422,
                "weak_password",
                "Password does not meet the security policy.",
                details=problems,
            )

        if await self._users.get_by_email(normalized_email) is not None:
            raise _duplicate_email_error()

        default_role = await self._users.get_role_by_code(RoleCode.USER)
        if default_role is None:
            logger.error("Role '%s' is missing from the database", RoleCode.USER)
            raise ApiError(
                500,
                "rbac_not_initialized",
                "System roles are not configured. Apply database migrations.",
            )

        try:
            user = await self._users.add(
                email=normalized_email,
                password_hash=hash_password(password),
                display_name=display_name,
                roles=[default_role],
            )
            await self._session.commit()
        except IntegrityError as exc:  # concurrent registration with the same email
            await self._session.rollback()
            raise _duplicate_email_error() from exc

        logger.info("Registered user %s", user.id)
        return user

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return await self._users.get_by_id(user_id)

    async def update_display_name(self, user: User, display_name: str) -> User:
        """Update only the display name; email, roles and flags stay untouched."""
        user.display_name = display_name
        await self._session.commit()
        logger.info("Updated profile of user %s", user.id)
        return user
