"""Authentication logic: password check and access-token issuance."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.core.security import (
    create_access_token,
    hash_password,
    normalize_email,
    password_needs_rehash,
    verify_password,
)
from app.modules.users.models import User
from app.modules.users.repository import UserRepository

logger = logging.getLogger(__name__)


def _invalid_credentials() -> ApiError:
    return ApiError(401, "invalid_credentials", "Invalid email or password.")


# Verified against when the email is unknown, so a failed login costs roughly the
# same time whether or not the account exists (reduces user enumeration).
_DUMMY_HASH = hash_password("timing-equalisation-placeholder")


class AuthService:
    """Password authentication for the API."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)

    async def authenticate(self, *, email: str, password: str) -> User:
        """Validate credentials and account state.

        Raises:
            ApiError: 401 for wrong credentials, 403 for a deactivated account.
        """
        user = await self._users.get_by_email(normalize_email(email))

        if user is None:
            verify_password(password, _DUMMY_HASH)
            raise _invalid_credentials()

        if not verify_password(password, user.password_hash):
            raise _invalid_credentials()

        if not user.is_active:
            raise ApiError(403, "account_inactive", "This account is deactivated.")

        if password_needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
            await self._session.commit()
            logger.info("Rehashed password for user %s", user.id)

        return user

    @staticmethod
    def issue_access_token(user: User) -> tuple[str, int]:
        return create_access_token(user.id)
