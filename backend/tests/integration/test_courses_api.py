"""Authoring API tests: lifecycle, ownership, slug rules and publication."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.integration.helpers import (
    add_lesson,
    add_module,
    bearer,
    category_id,
    create_category,
    create_course,
    create_course_or_fail,
    create_published_course,
    delete_category,
    register_admin,
    register_and_token,
    register_course_author,
    set_category_active,
)

pytestmark = pytest.mark.integration


async def test_create_course_is_a_draft_owned_by_the_caller(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    token, user = await register_course_author(client, session_factory)
    category = await category_id(client)

    response = await create_course(client, token, category)

    assert response.status_code == 201, response.text
    course = response.json()
    assert course["status"] == "draft"
    assert course["author_id"] == user["id"]
    assert course["category"]["slug"] == "programming"
    assert course["slug"] == "python-s-nulya"
    assert course["published_at"] is None
    assert course["modules"] == []
    assert course["modules_count"] == 0
    assert course["lessons_count"] == 0

    # A draft must never leak into the public catalog.
    catalog = await client.get("/api/v1/catalog/courses")
    assert catalog.json()["total"] == 0


async def test_client_cannot_smuggle_server_fields(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    token, _ = await register_course_author(client, session_factory)
    category = await category_id(client)

    for field, value in (
        ("author_id", "00000000-0000-0000-0000-000000000000"),
        ("status", "published"),
        ("slug", "forced-slug"),
        ("published_at", "2020-01-01T00:00:00Z"),
    ):
        response = await create_course(client, token, category, **{field: value})
        assert response.status_code == 422, field
        assert response.json()["error"]["code"] == "validation_error"


async def test_creation_validates_input(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    token, _ = await register_course_author(client, session_factory)
    category = await category_id(client)

    short_title = await create_course(client, token, category, title="Py")
    assert short_title.status_code == 422

    bad_level = await create_course(client, token, category, level="expert")
    assert bad_level.status_code == 422

    bad_language = await create_course(client, token, category, language="russian")
    assert bad_language.status_code == 422

    bad_cover = await create_course(client, token, category, cover_image_url="javascript:alert(1)")
    assert bad_cover.status_code == 422

    missing_category = await client.post(
        "/api/v1/courses",
        json={
            "title": "Курс без категории",
            "short_description": "Достаточно длинное краткое описание.",
            "description": "Достаточно длинное полное описание курса для проверки.",
        },
        headers=bearer(token),
    )
    assert missing_category.status_code == 422

    unknown_category = await create_course(
        client, token, "00000000-0000-0000-0000-000000000000"
    )
    assert unknown_category.status_code == 404
    assert unknown_category.json()["error"]["code"] == "category_not_found"


async def test_plain_user_cannot_create_courses(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    token, _ = await register_and_token(client)
    category = await category_id(client)

    response = await create_course(client, token, category)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "insufficient_permissions"


async def test_anonymous_cannot_create_courses(client: AsyncClient) -> None:
    category = await category_id(client)
    response = await client.post(
        "/api/v1/courses",
        json={
            "title": "Анонимный курс",
            "short_description": "Достаточно длинное краткое описание.",
            "description": "Достаточно длинное полное описание курса для проверки.",
            "category_id": category,
        },
    )
    assert response.status_code == 401


async def test_slug_is_unique_and_immutable(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    token, _ = await register_course_author(client, session_factory)
    category = await category_id(client)

    first = await create_course_or_fail(client, token, category)
    second = await create_course_or_fail(client, token, category)
    assert first["slug"] == "python-s-nulya"
    assert second["slug"] == "python-s-nulya-2"

    renamed = await client.patch(
        f"/api/v1/courses/{first['id']}",
        json={"title": "Python: полный курс"},
        headers=bearer(token),
    )
    assert renamed.status_code == 200, renamed.text
    body = renamed.json()
    assert body["title"] == "Python: полный курс"
    # Published links must keep working, so the slug never changes.
    assert body["slug"] == first["slug"]


async def test_author_sees_only_own_courses(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    author_a, _ = await register_course_author(client, session_factory, email="a@example.com")
    author_b, _ = await register_course_author(client, session_factory, email="b@example.com")
    category = await category_id(client)

    await create_course_or_fail(client, author_a, category)
    await create_course_or_fail(client, author_a, category, title="Второй курс автора")
    await create_course_or_fail(client, author_b, category, title="Курс другого автора")

    mine = await client.get("/api/v1/courses/mine", headers=bearer(author_a))
    assert mine.status_code == 200, mine.text
    page = mine.json()
    assert page["total"] == 2
    assert all(item["author_id"] != "" for item in page["items"])
    assert {item["title"] for item in page["items"]} == {
        "Python с нуля",
        "Второй курс автора",
    }

    paged = await client.get(
        "/api/v1/courses/mine?page=1&page_size=1", headers=bearer(author_a)
    )
    assert paged.json()["pages"] == 2
    assert len(paged.json()["items"]) == 1


async def test_foreign_course_is_hidden_behind_404(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    owner, _ = await register_course_author(client, session_factory, email="owner@example.com")
    intruder, _ = await register_course_author(
        client, session_factory, email="intruder@example.com"
    )
    category = await category_id(client)
    course = await create_course_or_fail(client, owner, category)
    module = await add_module(client, owner, course["id"])
    lesson = await add_lesson(client, owner, course["id"], module["id"])

    for method, url in (
        ("get", f"/api/v1/courses/{course['id']}"),
        ("patch", f"/api/v1/courses/{course['id']}"),
        ("post", f"/api/v1/courses/{course['id']}/publish"),
        ("post", f"/api/v1/courses/{course['id']}/unpublish"),
        ("post", f"/api/v1/courses/{course['id']}/archive"),
        ("delete", f"/api/v1/courses/{course['id']}"),
        ("post", f"/api/v1/courses/{course['id']}/modules"),
        ("delete", f"/api/v1/courses/{course['id']}/modules/{module['id']}"),
        (
            "patch",
            f"/api/v1/courses/{course['id']}/modules/{module['id']}/lessons/{lesson['id']}",
        ),
    ):
        kwargs = {"headers": bearer(intruder)}
        if method in {"patch", "post"} and url.endswith("/modules"):
            kwargs["json"] = {"title": "Взлом"}
        elif method == "patch":
            kwargs["json"] = {"title": "Взлом"}
        response = await getattr(client, method)(url, **kwargs)
        assert response.status_code == 404, f"{method.upper()} {url} -> {response.status_code}"
        assert response.json()["error"]["code"] == "course_not_found"

    # The intruder's failed attempts changed nothing.
    still_there = await client.get(
        f"/api/v1/courses/{course['id']}", headers=bearer(owner)
    )
    assert still_there.status_code == 200
    assert still_there.json()["modules"][0]["lessons"][0]["title"] == "Урок 1"


async def test_admin_manages_any_course(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    author, _ = await register_course_author(client, session_factory)
    admin, _ = await register_admin(client, session_factory)
    category = await category_id(client)
    course = await create_course_or_fail(client, author, category)
    module = await add_module(client, author, course["id"])
    await add_lesson(client, author, course["id"], module["id"])

    read = await client.get(f"/api/v1/courses/{course['id']}", headers=bearer(admin))
    assert read.status_code == 200

    updated = await client.patch(
        f"/api/v1/courses/{course['id']}",
        json={"short_description": "Обновлено администратором платформы."},
        headers=bearer(admin),
    )
    assert updated.status_code == 200, updated.text

    published = await client.post(
        f"/api/v1/courses/{course['id']}/publish", headers=bearer(admin)
    )
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "published"
    assert published.json()["published_at"] is not None

    archived = await client.post(
        f"/api/v1/courses/{course['id']}/archive", headers=bearer(admin)
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"


async def test_publish_requires_complete_content(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    token, _ = await register_course_author(client, session_factory)
    category = await category_id(client)

    empty = await create_course_or_fail(client, token, category)
    response = await client.post(
        f"/api/v1/courses/{empty['id']}/publish", headers=bearer(token)
    )
    assert response.status_code == 422, response.text
    error = response.json()["error"]
    assert error["code"] == "course_not_ready"
    assert "modules" in error["details"]["missing"]

    module = await add_module(client, token, empty["id"])
    response = await client.post(
        f"/api/v1/courses/{empty['id']}/publish", headers=bearer(token)
    )
    assert response.status_code == 422
    assert "module_1_lessons" in response.json()["error"]["details"]["missing"]

    await add_lesson(client, token, empty["id"], module["id"])
    ok = await client.post(
        f"/api/v1/courses/{empty['id']}/publish", headers=bearer(token)
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "published"


async def test_publish_requires_active_category(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    token, _ = await register_course_author(client, session_factory)
    category = await create_category(
        session_factory, name="Временная категория", slug="temporary-publish"
    )
    try:
        course = await create_course_or_fail(client, token, str(category))
        module = await add_module(client, token, course["id"])
        await add_lesson(client, token, course["id"], module["id"])

        await set_category_active(session_factory, "temporary-publish", False)

        response = await client.post(
            f"/api/v1/courses/{course['id']}/publish", headers=bearer(token)
        )
        assert response.status_code == 422
        assert "active_category" in response.json()["error"]["details"]["missing"]

        # An inactive category cannot receive a course through a PATCH either.
        other = await category_id(client, "design")
        moved = await client.patch(
            f"/api/v1/courses/{course['id']}",
            json={"category_id": other},
            headers=bearer(token),
        )
        assert moved.status_code == 200
        assert moved.json()["category"]["slug"] == "design"

        blocked = await client.patch(
            f"/api/v1/courses/{course['id']}",
            json={"category_id": str(category)},
            headers=bearer(token),
        )
        assert blocked.status_code == 422
        assert blocked.json()["error"]["code"] == "category_inactive"
    finally:
        await client.delete(
            f"/api/v1/courses/{course['id']}", headers=bearer(token)
        )
        await delete_category(session_factory, "temporary-publish")


async def test_republish_preserves_first_published_at(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    token, _ = await register_course_author(client, session_factory)
    category = await category_id(client)
    course = await create_published_course(client, token, category)
    first_published_at = course["published_at"]
    assert first_published_at is not None

    unpublished = await client.post(
        f"/api/v1/courses/{course['id']}/unpublish", headers=bearer(token)
    )
    assert unpublished.status_code == 200
    assert unpublished.json()["status"] == "draft"
    assert unpublished.json()["published_at"] == first_published_at
    assert (await client.get("/api/v1/catalog/courses")).json()["total"] == 0

    republished = await client.post(
        f"/api/v1/courses/{course['id']}/publish", headers=bearer(token)
    )
    assert republished.status_code == 200
    assert republished.json()["status"] == "published"
    assert republished.json()["published_at"] == first_published_at


async def test_archive_hides_without_deleting_and_delete_removes(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    token, _ = await register_course_author(client, session_factory)
    category = await category_id(client)
    course = await create_published_course(client, token, category)

    archived = await client.post(
        f"/api/v1/courses/{course['id']}/archive", headers=bearer(token)
    )
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert (await client.get("/api/v1/catalog/courses")).json()["total"] == 0

    # The record still exists for its author.
    readable = await client.get(
        f"/api/v1/courses/{course['id']}", headers=bearer(token)
    )
    assert readable.status_code == 200
    assert readable.json()["status"] == "archived"

    deleted = await client.delete(
        f"/api/v1/courses/{course['id']}", headers=bearer(token)
    )
    assert deleted.status_code == 204
    assert deleted.content == b""

    gone = await client.get(f"/api/v1/courses/{course['id']}", headers=bearer(token))
    assert gone.status_code == 404


async def test_course_update_validates_and_rejects_unknown_fields(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    token, _ = await register_course_author(client, session_factory)
    category = await category_id(client)
    course = await create_course_or_fail(client, token, category)

    unknown = await client.patch(
        f"/api/v1/courses/{course['id']}",
        json={"status": "published"},
        headers=bearer(token),
    )
    assert unknown.status_code == 422

    bad_level = await client.patch(
        f"/api/v1/courses/{course['id']}",
        json={"level": "guru"},
        headers=bearer(token),
    )
    assert bad_level.status_code == 422

    cleared_cover = await client.patch(
        f"/api/v1/courses/{course['id']}",
        json={"cover_image_url": None},
        headers=bearer(token),
    )
    assert cleared_cover.status_code == 200
    assert cleared_cover.json()["cover_image_url"] is None
