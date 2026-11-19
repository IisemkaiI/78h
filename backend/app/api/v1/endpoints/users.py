"""User profile endpoints (own profile only)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import SessionDep
from app.modules.auth.dependencies import require_permissions
from app.modules.users.models import User
from app.modules.users.rbac import PermissionCode
from app.modules.users.schemas import UpdateProfileRequest, UserRead
from app.modules.users.service import UserService

router = APIRouter(prefix="/users", tags=["Users"])

_AUTH_ERRORS = {
    401: {"description": "Not authenticated"},
    403: {"description": "Missing permission"},
}


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get own profile",
    description="Returns the authenticated user's profile with roles and permissions.",
    responses=_AUTH_ERRORS,
)
async def read_own_profile(
    user: Annotated[User, Depends(require_permissions(PermissionCode.PROFILE_READ))],
) -> UserRead:
    return UserRead.from_user(user)


@router.patch(
    "/me",
    response_model=UserRead,
    summary="Update own profile",
    description=(
        "Updates the display name only. UUID, email, roles, permissions and "
        "activity status cannot be changed through this endpoint: unknown fields "
        "are rejected with 422."
    ),
    responses={**_AUTH_ERRORS, 422: {"description": "Validation error"}},
)
async def update_own_profile(
    payload: UpdateProfileRequest,
    user: Annotated[User, Depends(require_permissions(PermissionCode.PROFILE_UPDATE))],
    session: SessionDep,
) -> UserRead:
    updated = await UserService(session).update_display_name(user, payload.display_name)
    return UserRead.from_user(updated)
