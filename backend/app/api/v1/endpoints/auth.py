"""Authentication endpoints: register, login, logout, current user."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.api.deps import SessionDep
from app.modules.auth.dependencies import CurrentUser
from app.modules.auth.service import AuthService
from app.modules.users.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserRead,
)
from app.modules.users.service import UserService

router = APIRouter(prefix="/auth", tags=["Authentication"])

_ERRORS = {
    401: {"description": "Invalid credentials or token"},
    403: {"description": "Account is deactivated"},
    409: {"description": "Email already registered"},
    422: {"description": "Validation error"},
}


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new account",
    description=(
        "Creates an account with the base `user` role and returns an access token. "
        "Privileged roles can never be requested through this endpoint: unknown "
        "fields are rejected by the schema."
    ),
    responses=_ERRORS,
)
async def register(payload: RegisterRequest, session: SessionDep) -> TokenResponse:
    user = await UserService(session).register(
        email=payload.email,
        password=payload.password,
        display_name=payload.display_name,
    )
    token, expires_in = AuthService.issue_access_token(user)
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserRead.from_user(user),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in with email and password",
    description=(
        "Verifies credentials and account state, then issues a short-lived JWT "
        "access token. The same error is returned for an unknown email and a "
        "wrong password."
    ),
    responses=_ERRORS,
)
async def login(payload: LoginRequest, session: SessionDep) -> TokenResponse:
    user = await AuthService(session).authenticate(
        email=payload.email,
        password=payload.password,
    )
    token, expires_in = AuthService.issue_access_token(user)
    return TokenResponse(
        access_token=token,
        expires_in=expires_in,
        user=UserRead.from_user(user),
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Log out (client-side)",
    description=(
        "Access tokens are stateless JWT: the server cannot revoke one before it "
        "expires. The client must delete the token; this endpoint exists so the "
        "operation is explicit and authenticated. Server-side revocation "
        "(denylist/refresh tokens) is planned for a later sprint."
    ),
    responses={401: {"description": "Not authenticated"}},
)
async def logout(_: CurrentUser, response: Response) -> Response:
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get the authenticated user",
    description="Returns the profile of the caller, including granted roles and permissions.",
    responses={401: {"description": "Not authenticated"}},
)
async def read_current_user(current_user: CurrentUser) -> UserRead:
    return UserRead.from_user(current_user)


@router.get(
    "/me/permissions",
    summary="List the caller's permissions",
    description="Convenience endpoint for diagnostics; the same data is embedded in `/auth/me`.",
    responses={401: {"description": "Not authenticated"}},
)
async def read_current_permissions(current_user: CurrentUser) -> dict[str, list[str]]:
    return {
        "roles": current_user.role_codes,
        "permissions": current_user.permission_codes,
    }
