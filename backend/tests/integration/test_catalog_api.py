"""Public catalog tests: visibility, search, filters and pagination."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.integration.helpers import (
    category_id,
    create_category,
    create_course,
    create_published_course,
    delete_category,
    list_categories,
    register_course_author,
    set_category_active,
)

pytestmark = pytest.mark.integration


async def test_categories_are_public(client: AsyncClient) -> None:
    categories = await list_categories(client)

    assert len(categories) == 8
    assert {item["slug"] for item in categories} == {
        "programming",
        "web-development",
        "game-development",
        "design",
        "information-technology",
        "data-analytics",
        "business-management",
        "foreign-languages",
    }
    assert all(item["is_active"] is True for item in categories)


async def test_inactive_category_is_hidden(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await create_category(
        session_factory, name="Скрытая", slug="temporary-hidden", is_active=False
    )
    try:
        slugs = {item["slug"] for item in await list_categories(client)}
        assert "temporary-hidden" not in slugs
        assert len(slugs) == 8
    finally:
        await delete_category(session_factory, "temporary-hidden")


async def test_published_course_appears_in_catalog(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    token, _ = await register_course_author(client, session_factory)
    category = await category_id(client)
    course = await create_published_course(client, token, category)

    response = await client.get("/api/v1/catalog/courses")

    assert response.status_code == 200
    page = response.json()
    assert page["total"] == 1
    assert page["pages"] == 1
    item = page["items"][0]
    assert item["slug"] == course["slug"]
    assert item["title"] == "Python с нуля"
    assert item["level"] == "beginner"
    assert item["language"] == "ru"
    assert item["category"]["slug"] == "programming"
    assert item["author"]["display_name"]
    assert item["modules_count"] == 1
    assert item["lessons_count"] == 1
    assert item["total_duration_minutes"] == 15

    detail = await client.get(f"/api/v1/catalog/courses/{course['slug']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["description"].startswith("Подробное введение")
    assert body["modules"][0]["title"] == "Модуль 1"
    lesson = body["modules"][0]["lessons"][0]
    assert lesson["title"] == "Урок 1"
    assert lesson["estimated_duration_minutes"] == 15
    # Lesson content is reserved for enrolled learners (Sprint 4).
    assert "content" not in lesson


async def test_drafts_and_archived_courses_are_hidden(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    token, _ = await register_course_author(client, session_factory)
    category = await category_id(client)

    draft = (await create_course(client, token, category)).json()
    catalog = await client.get("/api/v1/catalog/courses")
    assert catalog.json()["total"] == 0
    assert (await client.get(f"/api/v1/catalog/courses/{draft['slug']}")).status_code == 404

    published = await create_published_course(client, token, category)
    archive = await client.post(
        f"/api/v1/courses/{published['id']}/archive",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert archive.status_code == 200
    assert archive.json()["status"] == "archived"
    assert (await client.get("/api/v1/catalog/courses")).json()["total"] == 0
    assert (
        await client.get(f"/api/v1/catalog/courses/{published['slug']}")
    ).status_code == 404


async def test_search_filters_and_pagination(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    token, _ = await register_course_author(client, session_factory)
    programming = await category_id(client, "programming")
    web = await category_id(client, "web-development")
    analytics = await category_id(client, "data-analytics")

    await create_published_course(
        client, token, programming, title="Python с нуля", level="beginner"
    )
    await create_published_course(
        client,
        token,
        web,
        title="JavaScript для веба",
        level="intermediate",
        short_description="Фронтенд-разработка: DOM, события и современный JavaScript.",
    )
    await create_published_course(
        client,
        token,
        analytics,
        title="Аналитика данных",
        level="advanced",
        short_description="Статистика, визуализация и машинное обучение.",
    )
    # Draft must never contribute to totals.
    await create_course(client, token, programming, title="Python: продолжение")

    all_courses = (await client.get("/api/v1/catalog/courses")).json()
    assert all_courses["total"] == 3

    by_search = (await client.get("/api/v1/catalog/courses?search=python")).json()
    assert by_search["total"] == 1
    assert by_search["items"][0]["title"] == "Python с нуля"

    case_insensitive = (await client.get("/api/v1/catalog/courses?search=PYTHON")).json()
    assert case_insensitive["total"] == 1

    by_category = (await client.get("/api/v1/catalog/courses?category=web-development")).json()
    assert by_category["total"] == 1
    assert by_category["items"][0]["title"] == "JavaScript для веба"

    by_level = (await client.get("/api/v1/catalog/courses?level=advanced")).json()
    assert by_level["total"] == 1
    assert by_level["items"][0]["title"] == "Аналитика данных"

    by_language = (await client.get("/api/v1/catalog/courses?language=en")).json()
    assert by_language["total"] == 0

    first_page = (await client.get("/api/v1/catalog/courses?page=1&page_size=2")).json()
    assert first_page["pages"] == 2
    assert len(first_page["items"]) == 2

    second_page = (await client.get("/api/v1/catalog/courses?page=2&page_size=2")).json()
    assert len(second_page["items"]) == 1

    beyond = (await client.get("/api/v1/catalog/courses?page=5&page_size=2")).json()
    assert beyond["items"] == []
    assert beyond["total"] == 3

    invalid = await client.get("/api/v1/catalog/courses?level=expert")
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"


async def test_inactive_category_hides_its_published_courses(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    token, _ = await register_course_author(client, session_factory)
    category = await create_category(session_factory, name="Временная", slug="temporary-active")
    try:
        course = await create_published_course(client, token, str(category))
        assert (await client.get("/api/v1/catalog/courses")).json()["total"] == 1

        await set_category_active(session_factory, "temporary-active", False)

        assert (await client.get("/api/v1/catalog/courses")).json()["total"] == 0
        assert (
            await client.get(f"/api/v1/catalog/courses/{course['slug']}")
        ).status_code == 404

        # The author still sees the course in their own workspace.
        own = await client.get(
            f"/api/v1/courses/{course['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert own.status_code == 200
    finally:
        await client.delete(
            f"/api/v1/courses/{course['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        await delete_category(session_factory, "temporary-active")
