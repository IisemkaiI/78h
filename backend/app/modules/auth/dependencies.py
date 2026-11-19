"""Reusable FastAPI dependencies for authentication, roles and permissions.

All access control decisions happen here, on the server. The frontend never
decides what a user may do — it only reflects what the API allows.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.deps import SessionDep
from app.core.errors import ApiError
from app.core.security import decode_access_token
from app.modules.users.models import User
from app.modules.users.repository import UserRepository

_BEARER = HTTPBearer(
    auto_error=False,
    scheme_name="BearerAuth",
    description="JWT access token obtained from POST /api/v1/auth/login.",
)

_UNAUTHENTICATED_HEADERS = {"WWW-Authenticate": "Bearer"}


def _unauthenticated(code: str = "not_authenticated", message: str = "Authentication required.") -> ApiError:
    return ApiError(401, code, message, headers=_UNAUTHENTICATED_HEADERS)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_BEARER)],
    session: SessionDep,
) -> User:
    """Resolve the caller from a Bearer token.

    Rejects missing, malformed, expired and orphaned tokens with 401, and
    deactivated accounts with 403.
    """
    if credentials is None or not credentials.credentials:
        raise _unauthenticated()

    payload = decode_access_token(credentials.credentials)

    try:
        user_id = uuid.UUID(str(payload.get("sub")))
    except (TypeError, ValueError) as exc:
        raise _unauthenticated("invalid_token", "Access token is invalid.") from exc

    user = await UserRepository(session).get_by_id(user_id)
    if user is None:
        raise _unauthenticated("invalid_token", "Access token is invalid.")

    if not user.is_active:
        raise ApiError(403, "account_inactive", "This account is deactivated.")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*codes: str) -> Callable[..., Awaitable[User]]:
    """Require at least one of the given role codes (any-of semantics)."""
    if not codes:
        raise ValueError("require_roles() needs at least one role code")

    required = tuple(codes)

    async def dependency(current_user: CurrentUser) -> User:
        if not current_user.has_role(*required):
            raise ApiError(
                403,
                "insufficient_roles",
                "You do not have the required role.",
                details={"required": list(required), "granted": current_user.role_codes},
            )
        return current_user

    return dependency


def require_permissions(*codes: str) -> Callable[..., Awaitable[User]]:
    """Require every listed permission (all-of semantics)."""
    if not codes:
        raise ValueError("require_permissions() needs at least one permission code")

    required = tuple(codes)

    async def dependency(current_user: CurrentUser) -> User:
        granted = set(current_user.permission_codes)
        missing = [code for code in required if code not in granted]
        if missing:
            raise ApiError(
                403,
                "insufficient_permissions",
                "You do not have the required permission.",
                details={"missing": missing},
            )
        return current_user

    return dependency
