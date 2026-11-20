"""Helpers shared by the PostgreSQL-backed API tests."""

from __future__ import annotations

import uuid
from typing import Any

from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.users.models import Role, User
from app.modules.users.rbac import RoleCode

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


# --- Sprint 2: courses ----------------------------------------------------

COURSE_DEFAULTS: dict[str, Any] = {
    "title": "Python с нуля",
    "short_description": "Базовый курс программирования на Python для начинающих.",
    "description": (
        "Подробное введение в Python: синтаксис, типы данных, функции и первые "
        "небольшие проекты."
    ),
    "level": "beginner",
    "language": "ru",
}


async def list_categories(client: AsyncClient) -> list[dict[str, Any]]:
    response = await client.get("/api/v1/catalog/categories")
    assert response.status_code == 200, response.text
    return response.json()


async def category_id(client: AsyncClient, slug: str = "programming") -> str:
    for category in await list_categories(client):
        if category["slug"] == slug:
            return category["id"]
    raise AssertionError(f"Category {slug!r} is not seeded")


async def create_course(
    client: AsyncClient,
    token: str,
    category: str,
    **overrides: Any,
) -> Response:
    payload = {**COURSE_DEFAULTS, "category_id": category, **overrides}
    return await client.post("/api/v1/courses", json=payload, headers=bearer(token))


async def create_course_or_fail(
    client: AsyncClient,
    token: str,
    category: str,
    **overrides: Any,
) -> dict[str, Any]:
    response = await create_course(client, token, category, **overrides)
    assert response.status_code == 201, response.text
    return response.json()


async def add_module(
    client: AsyncClient,
    token: str,
    course_id: str,
    title: str = "Модуль 1",
) -> dict[str, Any]:
    response = await client.post(
        f"/api/v1/courses/{course_id}/modules",
        json={"title": title},
        headers=bearer(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


async def add_lesson(
    client: AsyncClient,
    token: str,
    course_id: str,
    module_id: str,
    title: str = "Урок 1",
    **overrides: Any,
) -> dict[str, Any]:
    payload = {
        "title": title,
        "description": "Краткое описание урока.",
        "content": "# Заголовок\n\nТекст урока в Markdown.",
        "estimated_duration_minutes": 15,
        **overrides,
    }
    response = await client.post(
        f"/api/v1/courses/{course_id}/modules/{module_id}/lessons",
        json=payload,
        headers=bearer(token),
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_published_course(
    client: AsyncClient,
    token: str,
    category: str,
    *,
    title: str = "Python с нуля",
    level: str = "beginner",
    language: str = "ru",
    short_description: str | None = None,
) -> dict[str, Any]:
    overrides: dict[str, Any] = {"title": title, "level": level, "language": language}
    if short_description is not None:
        overrides["short_description"] = short_description
    course = await create_course_or_fail(client, token, category, **overrides)
    module = await add_module(client, token, course["id"])
    await add_lesson(client, token, course["id"], module["id"])

    response = await client.post(
        f"/api/v1/courses/{course['id']}/publish",
        headers=bearer(token),
    )
    assert response.status_code == 200, response.text
    return response.json()


async def register_with_role(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    role_code: str,
    *,
    email: str,
) -> tuple[str, dict[str, Any]]:
    """Register an account, then grant it a role through the persistence layer.

    Public registration always assigns only ``user``; this helper mimics the
    administrative CLI for tests.
    """
    token, user = await register_and_token(client, email=email)
    await assign_role(session_factory, user["id"], role_code)
    return token, user


async def register_course_author(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    email: str = "author@example.com",
) -> tuple[str, dict[str, Any]]:
    return await register_with_role(
        client, session_factory, RoleCode.COURSE_AUTHOR, email=email
    )


async def register_admin(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    email: str = "admin@example.com",
) -> tuple[str, dict[str, Any]]:
    return await register_with_role(client, session_factory, RoleCode.ADMIN, email=email)


async def create_category(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    name: str,
    slug: str,
    is_active: bool = True,
) -> uuid.UUID:
    """Insert a category directly (category administration ships in Sprint 8)."""
    from app.modules.courses.models.category import Category

    async with session_factory() as session:
        category = Category(name=name, slug=slug, is_active=is_active)
        session.add(category)
        await session.commit()
        return category.id


async def set_category_active(
    session_factory: async_sessionmaker[AsyncSession],
    slug: str,
    is_active: bool,
) -> None:
    from app.modules.courses.models.category import Category

    async with session_factory() as session:
        category = await session.scalar(select(Category).where(Category.slug == slug))
        assert category is not None
        category.is_active = is_active
        await session.commit()


async def delete_category(
    session_factory: async_sessionmaker[AsyncSession], slug: str
) -> None:
    from sqlalchemy import delete

    from app.modules.courses.models.category import Category

    async with session_factory() as session:
        await session.execute(delete(Category).where(Category.slug == slug))
        await session.commit()


# --- Sprint 4: learning ---------------------------------------------------


async def enroll(
    client: AsyncClient, token: str, course_id: str
) -> Response:
    return await client.post(
        "/api/v1/learning/enrollments",
        json={"course_id": course_id},
        headers=bearer(token),
    )


async def enroll_or_fail(
    client: AsyncClient, token: str, course_id: str
) -> dict[str, Any]:
    response = await enroll(client, token, course_id)
    assert response.status_code in {200, 201}, response.text
    return response.json()


async def set_lesson_state(
    client: AsyncClient,
    token: str,
    enrollment_id: str,
    lesson_id: str,
    state: str,
) -> Response:
    return await client.put(
        f"/api/v1/learning/enrollments/{enrollment_id}/lessons/{lesson_id}/progress",
        json={"state": state},
        headers=bearer(token),
    )


async def get_learning_course(
    client: AsyncClient, token: str, slug: str
) -> Response:
    return await client.get(
        f"/api/v1/learning/courses/{slug}",
        headers=bearer(token),
    )

