"""Course structure tests: modules, lessons, ordering and ownership chains."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.integration.helpers import (
    add_lesson,
    add_module,
    bearer,
    category_id,
    create_course_or_fail,
    register_admin,
    register_and_token,
    register_course_author,
)

pytestmark = pytest.mark.integration


async def _course_with_structure(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    email: str = "author@example.com",
) -> tuple[str, dict]:
    token, _ = await register_course_author(client, session_factory, email=email)
    category = await category_id(client)
    course = await create_course_or_fail(client, token, category)
    return token, course


async def test_modules_are_appended_with_contiguous_positions(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    token, course = await _course_with_structure(client, session_factory)

    first = await add_module(client, token, course["id"], title="Введение")
    second = await add_module(client, token, course["id"], title="Основы")
    third = await add_module(client, token, course["id"], title="Практика")

    assert (first["position"], second["position"], third["position"]) == (1, 2, 3)

    detail = await client.get(f"/api/v1/courses/{course['id']}", headers=bearer(token))
    assert [module["title"] for module in detail.json()["modules"]] == [
        "Введение",
        "Основы",
        "Практика",
    ]
    assert detail.json()["modules_count"] == 3


async def test_reorder_modules(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    token, course = await _course_with_structure(client, session_factory)
    first = await add_module(client, token, course["id"], title="Первый")
    second = await add_module(client, token, course["id"], title="Второй")
    third = await add_module(client, token, course["id"], title="Третий")

    response = await client.put(
        f"/api/v1/courses/{course['id']}/modules/order",
        json={"ids": [third["id"], first["id"], second["id"]]},
        headers=bearer(token),
    )

    assert response.status_code == 200, response.text
    ordered = response.json()
    assert [module["title"] for module in ordered] == ["Третий", "Первый", "Второй"]
    assert [module["position"] for module in ordered] == [1, 2, 3]

    detail = await client.get(f"/api/v1/courses/{course['id']}", headers=bearer(token))
    assert [module["title"] for module in detail.json()["modules"]] == [
        "Третий",
        "Первый",
        "Второй",
    ]


async def test_reorder_rejects_incomplete_or_foreign_ids(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    token, course = await _course_with_structure(client, session_factory)
    first = await add_module(client, token, course["id"], title="Первый")
    second = await add_module(client, token, course["id"], title="Второй")
    other_course = await create_course_or_fail(
        client, token, await category_id(client), title="Другой курс"
    )
    foreign = await add_module(client, token, other_course["id"], title="Чужой модуль")

    for ids in (
        [first["id"]],
        [first["id"], first["id"]],
        [first["id"], foreign["id"]],
    ):
        response = await client.put(
            f"/api/v1/courses/{course['id']}/modules/order",
            json={"ids": ids},
            headers=bearer(token),
        )
        assert response.status_code == 422, ids
        assert response.json()["error"]["code"] == "invalid_order"

    # The original order is unchanged after the failed attempts.
    detail = await client.get(f"/api/v1/courses/{course['id']}", headers=bearer(token))
    assert [module["id"] for module in detail.json()["modules"]] == [
        first["id"],
        second["id"],
    ]


async def test_lessons_are_ordered_and_reorderable(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    token, course = await _course_with_structure(client, session_factory)
    module = await add_module(client, token, course["id"])
    first = await add_lesson(client, token, course["id"], module["id"], title="Первый урок")
    second = await add_lesson(
        client, token, course["id"], module["id"], title="Второй урок"
    )
    third = await add_lesson(
        client, token, course["id"], module["id"], title="Третий урок"
    )
    assert (first["position"], second["position"], third["position"]) == (1, 2, 3)

    response = await client.put(
        f"/api/v1/courses/{course['id']}/modules/{module['id']}/lessons/order",
        json={"ids": [third["id"], second["id"], first["id"]]},
        headers=bearer(token),
    )

    assert response.status_code == 200, response.text
    ordered = response.json()
    assert [lesson["title"] for lesson in ordered] == [
        "Третий урок",
        "Второй урок",
        "Первый урок",
    ]
    assert [lesson["position"] for lesson in ordered] == [1, 2, 3]

    invalid = await client.put(
        f"/api/v1/courses/{course['id']}/modules/{module['id']}/lessons/order",
        json={"ids": [first["id"]]},
        headers=bearer(token),
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_order"


async def test_lesson_validation_and_markdown_content(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    token, course = await _course_with_structure(client, session_factory)
    module = await add_module(client, token, course["id"])
    url = f"/api/v1/courses/{course['id']}/modules/{module['id']}/lessons"

    blank_title = await client.post(
        url,
        json={"title": "   ", "estimated_duration_minutes": 5},
        headers=bearer(token),
    )
    assert blank_title.status_code == 422

    negative = await client.post(
        url,
        json={"title": "Нормальный урок", "estimated_duration_minutes": -1},
        headers=bearer(token),
    )
    assert negative.status_code == 422

    lesson = await add_lesson(
        client,
        token,
        course["id"],
        module["id"],
        content="## Раздел\n\n```python\nprint('hi')\n```",
        estimated_duration_minutes=0,
    )
    assert lesson["estimated_duration_minutes"] == 0
    assert lesson["content"].startswith("## Раздел")

    updated = await client.patch(
        f"{url}/{lesson['id']}",
        json={
            "title": "  Обновлённый   урок  ",
            "content": "Новый текст",
            "estimated_duration_minutes": 42,
        },
        headers=bearer(token),
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["title"] == "Обновлённый урок"
    assert body["content"] == "Новый текст"
    assert body["estimated_duration_minutes"] == 42

    empty_patch = await client.patch(
        f"{url}/{lesson['id']}",
        json={"title": ""},
        headers=bearer(token),
    )
    assert empty_patch.status_code == 422


async def test_delete_module_cascades_lessons_and_renumbers(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    token, course = await _course_with_structure(client, session_factory)
    modules = []
    lessons = {}
    for index in range(1, 4):
        module = await add_module(client, token, course["id"], title=f"Модуль {index}")
        modules.append(module)
        lessons[module["id"]] = [
            await add_lesson(
                client,
                token,
                course["id"],
                module["id"],
                title=f"Урок {index}.{lesson_index}",
                estimated_duration_minutes=10,
            )
            for lesson_index in (1, 2)
        ]

    removed = modules[1]
    removed_lesson_ids = {lesson["id"] for lesson in lessons[removed["id"]]}

    response = await client.delete(
        f"/api/v1/courses/{course['id']}/modules/{removed['id']}",
        headers=bearer(token),
    )
    assert response.status_code == 204

    detail = (
        await client.get(f"/api/v1/courses/{course['id']}", headers=bearer(token))
    ).json()
    assert [module["position"] for module in detail["modules"]] == [1, 2]
    assert [module["title"] for module in detail["modules"]] == ["Модуль 1", "Модуль 3"]
    assert detail["modules_count"] == 2
    assert detail["lessons_count"] == 4
    assert detail["total_duration_minutes"] == 40

    surviving_lesson_ids = {
        lesson["id"]
        for module in detail["modules"]
        for lesson in module["lessons"]
    }
    assert surviving_lesson_ids.isdisjoint(removed_lesson_ids)

    # Cascaded lessons cannot be addressed any more.
    stale = await client.patch(
        f"/api/v1/courses/{course['id']}/modules/{removed['id']}/lessons/"
        f"{next(iter(removed_lesson_ids))}",
        json={"title": "Призрак"},
        headers=bearer(token),
    )
    assert stale.status_code == 404


async def test_delete_lesson_renumbers_remaining(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    token, course = await _course_with_structure(client, session_factory)
    module = await add_module(client, token, course["id"])
    first = await add_lesson(client, token, course["id"], module["id"], title="Первый")
    second = await add_lesson(client, token, course["id"], module["id"], title="Второй")
    third = await add_lesson(client, token, course["id"], module["id"], title="Третий")

    response = await client.delete(
        f"/api/v1/courses/{course['id']}/modules/{module['id']}/lessons/{second['id']}",
        headers=bearer(token),
    )
    assert response.status_code == 204

    detail = (
        await client.get(f"/api/v1/courses/{course['id']}", headers=bearer(token))
    ).json()
    remaining = detail["modules"][0]["lessons"]
    assert [lesson["id"] for lesson in remaining] == [first["id"], third["id"]]
    assert [lesson["position"] for lesson in remaining] == [1, 2]
    assert detail["lessons_count"] == 2


async def test_structure_checks_the_whole_ownership_chain(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    owner, course = await _course_with_structure(
        client, session_factory, email="owner@example.com"
    )
    intruder, _ = await register_course_author(
        client, session_factory, email="intruder@example.com"
    )
    module = await add_module(client, owner, course["id"])
    lesson = await add_lesson(client, owner, course["id"], module["id"])

    attempts = (
        ("post", f"/api/v1/courses/{course['id']}/modules", {"title": "Взлом"}),
        (
            "patch",
            f"/api/v1/courses/{course['id']}/modules/{module['id']}",
            {"title": "Взлом"},
        ),
        (
            "delete",
            f"/api/v1/courses/{course['id']}/modules/{module['id']}",
            None,
        ),
        (
            "post",
            f"/api/v1/courses/{course['id']}/modules/{module['id']}/lessons",
            {"title": "Взлом"},
        ),
        (
            "patch",
            f"/api/v1/courses/{course['id']}/modules/{module['id']}/lessons/{lesson['id']}",
            {"title": "Взлом"},
        ),
        (
            "delete",
            f"/api/v1/courses/{course['id']}/modules/{module['id']}/lessons/{lesson['id']}",
            None,
        ),
        (
            "put",
            f"/api/v1/courses/{course['id']}/modules/order",
            {"ids": [module["id"]]},
        ),
        (
            "put",
            f"/api/v1/courses/{course['id']}/modules/{module['id']}/lessons/order",
            {"ids": [lesson["id"]]},
        ),
    )

    for method, url, payload in attempts:
        kwargs = {"headers": bearer(intruder)}
        if payload is not None:
            kwargs["json"] = payload
        response = await getattr(client, method)(url, **kwargs)
        assert response.status_code == 404, f"{method.upper()} {url}"
        assert response.json()["error"]["code"] == "course_not_found"

    intact = (
        await client.get(f"/api/v1/courses/{course['id']}", headers=bearer(owner))
    ).json()
    assert intact["modules"][0]["title"] == "Модуль 1"
    assert intact["modules"][0]["lessons"][0]["title"] == "Урок 1"


async def test_module_from_another_course_is_not_addressable(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    token, course = await _course_with_structure(client, session_factory)
    other = await create_course_or_fail(
        client, token, await category_id(client), title="Второй курс автора"
    )
    foreign_module = await add_module(client, token, other["id"])

    response = await client.patch(
        f"/api/v1/courses/{course['id']}/modules/{foreign_module['id']}",
        json={"title": "Переезд"},
        headers=bearer(token),
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "module_not_found"


async def test_plain_user_and_guest_cannot_edit_structure(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    owner, course = await _course_with_structure(client, session_factory)
    module = await add_module(client, owner, course["id"])
    user_token, _ = await register_and_token(client, email="plain@example.com")

    forbidden = await client.post(
        f"/api/v1/courses/{course['id']}/modules",
        json={"title": "Попытка"},
        headers=bearer(user_token),
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "insufficient_permissions"

    anonymous = await client.post(
        f"/api/v1/courses/{course['id']}/modules",
        json={"title": "Попытка"},
    )
    assert anonymous.status_code == 401


async def test_admin_can_manage_structure_of_any_course(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    author, course = await _course_with_structure(client, session_factory)
    admin, _ = await register_admin(client, session_factory)

    module = await add_module(client, admin, course["id"], title="Модуль администратора")
    lesson = await add_lesson(
        client, admin, course["id"], module["id"], title="Урок администратора"
    )

    renamed = await client.patch(
        f"/api/v1/courses/{course['id']}/modules/{module['id']}",
        json={"title": "Переименовано"},
        headers=bearer(admin),
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Переименовано"

    detail = (
        await client.get(f"/api/v1/courses/{course['id']}", headers=bearer(author))
    ).json()
    assert detail["modules"][0]["title"] == "Переименовано"
    assert detail["modules"][0]["lessons"][0]["id"] == lesson["id"]
