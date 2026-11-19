"""Registration, login, logout and current-user endpoint tests (real PostgreSQL)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.modules.users.models import User
from tests.integration.helpers import (
    VALID_PASSWORD,
    bearer,
    load_user,
    login,
    register,
    register_and_token,
    set_active,
)

pytestmark = pytest.mark.integration


async def test_register_creates_user_with_base_role(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    response = await register(client, email="Ivan.Petrov@Example.COM", display_name="Иван Петров")

    assert response.status_code == 201, response.text
    body = response.json()

    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    assert body["access_token"]
    assert body["user"]["email"] == "ivan.petrov@example.com"
    assert body["user"]["display_name"] == "Иван Петров"
    assert body["user"]["is_active"] is True
    assert [role["code"] for role in body["user"]["roles"]] == ["user"]
    assert "profile:read" in body["user"]["permissions"]
    assert "profile:update" in body["user"]["permissions"]

    user = await load_user(session_factory, body["user"]["id"])
    assert user is not None
    assert user.email == "ivan.petrov@example.com"
    assert user.password_hash.startswith("$argon2id$")
    assert VALID_PASSWORD not in user.password_hash
    assert [role.code for role in user.roles] == ["user"]


async def test_register_response_never_exposes_password_material(client: AsyncClient) -> None:
    response = await register(client)

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"access_token", "token_type", "expires_in", "user"}
    user_fields = set(body["user"])
    assert "password" not in user_fields
    assert "password_hash" not in user_fields
    assert "argon2" not in response.text.lower()


async def test_register_rejects_duplicate_email(client: AsyncClient) -> None:
    assert (await register(client, email="dup@example.com")).status_code == 201

    response = await register(client, email="dup@example.com", display_name="Второй")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_already_registered"


async def test_register_is_case_insensitive_for_duplicates(client: AsyncClient) -> None:
    assert (await register(client, email="Case@Example.com")).status_code == 201

    response = await register(client, email="case@EXAMPLE.com")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_already_registered"


@pytest.mark.parametrize("email", ["not-an-email", "missing@", "@example.com", "a b@example.com"])
async def test_register_rejects_invalid_email(client: AsyncClient, email: str) -> None:
    response = await register(client, email=email)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


@pytest.mark.parametrize(
    "password",
    [
        "short1",  # too short
        "alllettersonly",  # no digit
        "12345678901",  # no letter
        "password123",  # deny-list
        "Str0ngPassw0rd! ",  # surrounding whitespace
    ],
)
async def test_register_rejects_weak_password(client: AsyncClient, password: str) -> None:
    response = await register(client, password=password)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_register_rejects_client_supplied_roles(client: AsyncClient) -> None:
    response = await register(client, roles=["admin"])

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert "roles" in response.text


async def test_register_rejects_other_privileged_fields(client: AsyncClient) -> None:
    response = await register(client, is_active=False)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_login_returns_token_and_profile(client: AsyncClient) -> None:
    await register(client, email="login@example.com")

    response = await login(client, email="LOGIN@example.com")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["access_token"]
    assert body["user"]["email"] == "login@example.com"
    assert [role["code"] for role in body["user"]["roles"]] == ["user"]


async def test_login_rejects_wrong_password(client: AsyncClient) -> None:
    await register(client, email="wrong@example.com")

    response = await login(client, email="wrong@example.com", password="Wr0ngPassw0rd!")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


async def test_login_rejects_unknown_email(client: AsyncClient) -> None:
    response = await login(client, email="nobody@example.com")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


async def test_login_rejects_inactive_user(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    _, user = await register_and_token(client, email="inactive@example.com")
    await set_active(session_factory, user["id"], False)

    response = await login(client, email="inactive@example.com")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "account_inactive"


async def test_me_returns_current_user(client: AsyncClient) -> None:
    token, user = await register_and_token(client, email="me@example.com")

    response = await client.get("/api/v1/auth/me", headers=bearer(token))

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == user["id"]
    assert body["email"] == "me@example.com"
    assert "password_hash" not in body


async def test_me_requires_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


async def test_me_rejects_invalid_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me", headers=bearer("not-a-jwt"))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


async def test_me_rejects_token_with_broken_signature(client: AsyncClient) -> None:
    token, _ = await register_and_token(client, email="signed@example.com")
    broken = token[:-2] + ("aa" if token[-2:] != "aa" else "bb")

    response = await client.get("/api/v1/auth/me", headers=bearer(broken))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


async def test_me_rejects_expired_token(client: AsyncClient) -> None:
    _, user = await register_and_token(client, email="expired@example.com")
    settings = get_settings()
    now = datetime.now(UTC)
    expired = jwt.encode(
        {
            "sub": user["id"],
            "type": "access",
            "iss": settings.jwt_issuer,
            "iat": int((now - timedelta(hours=2)).timestamp()),
            "exp": int((now - timedelta(hours=1)).timestamp()),
            "jti": "expired-test-token",
        },
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )

    response = await client.get("/api/v1/auth/me", headers=bearer(expired))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "token_expired"


async def test_token_lifetime_is_limited(client: AsyncClient) -> None:
    token, _ = await register_and_token(client)
    payload = jwt.decode(
        token,
        get_settings().jwt_secret.get_secret_value(),
        algorithms=[get_settings().jwt_algorithm],
        issuer=get_settings().jwt_issuer,
        options={"verify_exp": False},
    )

    lifetime = payload["exp"] - payload["iat"]
    assert lifetime == get_settings().access_token_expire_minutes * 60
    assert lifetime <= 24 * 60 * 60


async def test_token_for_deleted_user_is_rejected(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    token, user = await register_and_token(client, email="deleted@example.com")
    async with session_factory() as session:
        stored = await session.get(User, uuid.UUID(user["id"]))
        assert stored is not None
        await session.delete(stored)
        await session.commit()

    response = await client.get("/api/v1/auth/me", headers=bearer(token))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


async def test_logout_requires_authentication(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/logout")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


async def test_logout_returns_no_content(client: AsyncClient) -> None:
    token, _ = await register_and_token(client)

    response = await client.post("/api/v1/auth/logout", headers=bearer(token))

    assert response.status_code == 204
    assert response.content == b""
