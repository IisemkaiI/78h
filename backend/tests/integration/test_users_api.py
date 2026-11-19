"""Profile and RBAC tests (real PostgreSQL)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import ApiError
from app.modules.auth.dependencies import require_permissions, require_roles
from app.modules.users.rbac import PermissionCode, RoleCode
from tests.integration.helpers import (
    assign_role,
    bearer,
    clear_roles,
    load_user,
    register,
    register_and_token,
)

pytestmark = pytest.mark.integration


async def test_get_own_profile(client: AsyncClient) -> None:
    token, user = await register_and_token(client, email="profile@example.com")

    response = await client.get("/api/v1/users/me", headers=bearer(token))

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == user["id"]
    assert body["email"] == "profile@example.com"
    assert body["display_name"] == user["display_name"]
    assert [role["code"] for role in body["roles"]] == ["user"]
    assert "password_hash" not in body


async def test_get_own_profile_requires_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/users/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


async def test_update_display_name_is_persisted(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    token, user = await register_and_token(client, email="rename@example.com")

    response = await client.patch(
        "/api/v1/users/me", headers=bearer(token), json={"display_name": "  Новое   Имя  "}
    )

    assert response.status_code == 200, response.text
    assert response.json()["display_name"] == "Новое Имя"
    assert response.json()["email"] == "rename@example.com"

    stored = await load_user(session_factory, user["id"])
    assert stored is not None
    assert stored.display_name == "Новое Имя"

    refreshed = await client.get("/api/v1/users/me", headers=bearer(token))
    assert refreshed.json()["display_name"] == "Новое Имя"


@pytest.mark.parametrize(
    "payload",
    [
        {"display_name": "Новое Имя", "email": "attacker@example.com"},
        {"display_name": "Новое Имя", "roles": ["admin"]},
        {"display_name": "Новое Имя", "is_active": False},
        {"display_name": "Новое Имя", "permissions": ["admin:manage_users"]},
    ],
)
async def test_update_rejects_privileged_fields(client: AsyncClient, payload: dict) -> None:
    token, _ = await register_and_token(client, email="fields@example.com")

    response = await client.patch("/api/v1/users/me", headers=bearer(token), json=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize("display_name", ["a", "  ", "x" * 200])
async def test_update_rejects_invalid_display_name(
    client: AsyncClient, display_name: str
) -> None:
    token, _ = await register_and_token(client, email="invalid-name@example.com")

    response = await client.patch(
        "/api/v1/users/me", headers=bearer(token), json={"display_name": display_name}
    )

    assert response.status_code == 422


async def test_user_cannot_read_another_users_profile(client: AsyncClient) -> None:
    token, _ = await register_and_token(client, email="first@example.com")
    _, other = await register_and_token(client, email="second@example.com")

    detail = await client.get(f"/api/v1/users/{other['id']}", headers=bearer(token))
    update = await client.patch(
        f"/api/v1/users/{other['id']}",
        headers=bearer(token),
        json={"display_name": "Взлом"},
    )

    assert detail.status_code in (404, 405)
    assert update.status_code in (404, 405)


async def test_roles_are_additive_and_union_permissions(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    token, user = await register_and_token(client, email="multi-role@example.com")
    await assign_role(session_factory, user["id"], RoleCode.TEACHER)
    await assign_role(session_factory, user["id"], RoleCode.COURSE_AUTHOR)

    response = await client.get("/api/v1/auth/me", headers=bearer(token))

    assert response.status_code == 200
    body = response.json()
    assert {role["code"] for role in body["roles"]} == {"user", "teacher", "course_author"}
    assert "teaching:manage" in body["permissions"]
    assert "courses:create" in body["permissions"]
    assert "courses:publish" in body["permissions"]

    stored = await load_user(session_factory, user["id"])
    assert stored is not None
    assert set(stored.role_codes) == {"user", "teacher", "course_author"}


async def test_admin_role_grants_admin_permissions(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    token, user = await register_and_token(client, email="admin@example.com")
    await assign_role(session_factory, user["id"], RoleCode.ADMIN)

    response = await client.get("/api/v1/auth/me", headers=bearer(token))

    body = response.json()
    assert {role["code"] for role in body["roles"]} == {"user", "admin"}
    assert PermissionCode.ADMIN_MANAGE_ROLES in body["permissions"]
    assert PermissionCode.ADMIN_MANAGE_USERS in body["permissions"]


async def test_user_without_roles_is_forbidden(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    token, user = await register_and_token(client, email="roleless@example.com")
    await clear_roles(session_factory, user["id"])

    response = await client.get("/api/v1/users/me", headers=bearer(token))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "insufficient_permissions"


async def test_require_roles_requires_at_least_one_code() -> None:
    with pytest.raises(ValueError):
        require_roles()
    with pytest.raises(ValueError):
        require_permissions()


async def test_require_roles_dependency_denies_and_allows(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    _, user = await register_and_token(client, email="guard@example.com")
    normal = await load_user(session_factory, user["id"])
    assert normal is not None

    admin_dependency = require_roles(RoleCode.ADMIN)
    with pytest.raises(ApiError) as denied:
        await admin_dependency(normal)
    assert denied.value.status_code == 403
    assert denied.value.code == "insufficient_roles"

    await assign_role(session_factory, user["id"], RoleCode.ADMIN)
    admin = await load_user(session_factory, user["id"])
    assert admin is not None
    assert await admin_dependency(admin) is admin


async def test_require_permissions_dependency_requires_every_permission(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    _, user = await register_and_token(client, email="perms@example.com")
    normal = await load_user(session_factory, user["id"])
    assert normal is not None

    profile = require_permissions(
        PermissionCode.PROFILE_READ, PermissionCode.PROFILE_UPDATE
    )
    admin = require_permissions(PermissionCode.ADMIN_MANAGE_USERS)

    assert await profile(normal) is normal
    with pytest.raises(ApiError) as denied:
        await admin(normal)
    assert denied.value.status_code == 403
    assert denied.value.code == "insufficient_permissions"
    assert PermissionCode.ADMIN_MANAGE_USERS in denied.value.details["missing"]


async def test_no_public_registration_of_privileged_role(client: AsyncClient) -> None:
    response = await register(client, email="sneaky@example.com", role="admin")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_unauthenticated_user_cannot_update_profile(client: AsyncClient) -> None:
    response = await client.patch("/api/v1/users/me", json={"display_name": "Аноним"})

    assert response.status_code == 401
