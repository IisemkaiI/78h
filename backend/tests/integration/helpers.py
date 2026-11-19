"""Helpers shared by the PostgreSQL-backed API tests."""

from __future__ import annotations

import uuid
from typing import Any

from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.users.models import Role, User

VALID_PASSWORD = "Str0ngPassw0rd!"
REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def register(
    client: AsyncClient,
    *,
    email: str = "user@example.com",
    password: str = VALID_PASSWORD,
    display_name: str = "Тестовый Пользователь",
    **extra: Any,
) -> Response:
    payload: dict[str, Any] = {
        "email": email,
        "password": password,
        "display_name": display_name,
        **extra,
    }
    return await client.post(REGISTER_URL, json=payload)


async def register_and_token(
    client: AsyncClient,
    *,
    email: str = "user@example.com",
    password: str = VALID_PASSWORD,
    display_name: str = "Тестовый Пользователь",
) -> tuple[str, dict[str, Any]]:
    response = await register(
        client, email=email, password=password, display_name=display_name
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return body["access_token"], body["user"]


async def login(
    client: AsyncClient, *, email: str = "user@example.com", password: str = VALID_PASSWORD
) -> Response:
    return await client.post(LOGIN_URL, json={"email": email, "password": password})


async def assign_role(
    session_factory: async_sessionmaker[AsyncSession],
    user_id: str | uuid.UUID,
    role_code: str,
) -> None:
    """Attach a role through the persistence layer (simulates admin tooling)."""
    async with session_factory() as session:
        user = await session.get(User, uuid.UUID(str(user_id)))
        assert user is not None
        role = await session.scalar(select(Role).where(Role.code == role_code))
        assert role is not None
        if role not in user.roles:
            user.roles.append(role)
        await session.commit()


async def set_active(
    session_factory: async_sessionmaker[AsyncSession],
    user_id: str | uuid.UUID,
    is_active: bool,
) -> None:
    async with session_factory() as session:
        user = await session.get(User, uuid.UUID(str(user_id)))
        assert user is not None
        user.is_active = is_active
        await session.commit()


async def load_user(
    session_factory: async_sessionmaker[AsyncSession], user_id: str | uuid.UUID
) -> User | None:
    async with session_factory() as session:
        return await session.get(User, uuid.UUID(str(user_id)))


async def clear_roles(
    session_factory: async_sessionmaker[AsyncSession], user_id: str | uuid.UUID
) -> None:
    """Remove every role from a user (tests the permission guard)."""
    async with session_factory() as session:
        user = await session.get(User, uuid.UUID(str(user_id)))
        assert user is not None
        user.roles.clear()
        await session.commit()
