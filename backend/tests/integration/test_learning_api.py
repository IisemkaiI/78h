"""Sprint 4 integration tests on real PostgreSQL.

Covers enrollment lifecycle, protected lesson content, three-state progress,
structural reconciliation and deletion history.
"""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.integration.helpers import (
    add_lesson,
    add_module,
    bearer,
    category_id,
    clear_roles,
    create_course_or_fail,
    create_published_course,
    enroll,
    enroll_or_fail,
    get_learning_course,
    register_admin,
    register_and_token,
    register_course_author,
    set_lesson_state,
)

pytestmark = pytest.mark.integration


async def _two_lesson_course(
    client: AsyncClient,
    token: str,
    *,
    title: str = "Learning course",
) -> dict:
    category = await category_id(client)
    course = await create_course_or_fail(client, token, category, title=title)
    module = await add_module(client, token, course["id"], title="Module")
    first = await add_lesson(client, token, course["id"], module["id"], title="First")
    second = await add_lesson(client, token, course["id"], module["id"], title="Second")
    published = await client.post(
        f"/api/v1/courses/{course['id']}/publish",
        headers=bearer(token),
    )
    assert published.status_code == 200, published.text
    detail = published.json()
    return {
        "course": detail,
        "module": module,
        "lessons": [first, second],
    }


async def test_enrollment_lifecycle_and_reactivation(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    author_token, _ = await register_course_author(client, session_factory)
    learner_token, _ = await register_and_token(client, email="learner@example.com")
    category = await category_id(client)
    course = await create_published_course(client, author_token, category)

    created = await enroll(client, learner_token, course["id"])
    assert created.status_code == 201, created.text
    body = created.json()
    enrollment_id = body["id"]
    assert body["status"] == "active"
    assert body["course"]["slug"] == course["slug"]
    assert body["progress"]["total_lessons"] == 1
    assert body["progress"]["completed_lessons"] == 0
    assert body["progress"]["progress_percent"] == 0

    duplicate = await enroll(client, learner_token, course["id"])
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "already_enrolled"

    cancelled = await client.delete(
        f"/api/v1/learning/enrollments/{enrollment_id}",
        headers=bearer(learner_token),
    )
    assert cancelled.status_code == 204, cancelled.text

    status = await client.get(
        f"/api/v1/learning/enrollments/by-course/{course['id']}",
        headers=bearer(learner_token),
    )
    assert status.status_code == 200
    assert status.json()["enrolled"] is False
    assert status.json()["enrollment"]["status"] == "cancelled"

    reactivated = await enroll(client, learner_token, course["id"])
    assert reactivated.status_code == 200, reactivated.text
    assert reactivated.json()["id"] == enrollment_id
    assert reactivated.json()["status"] == "active"

    mine = await client.get(
        "/api/v1/learning/enrollments/mine",
        headers=bearer(learner_token),
    )
    assert mine.status_code == 200
    assert mine.json()["total"] == 1


async def test_enrollment_validation_and_author_restriction(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    author_token, _ = await register_course_author(client, session_factory)
    learner_token, _ = await register_and_token(client, email="learner2@example.com")
    category = await category_id(client)
    published = await create_published_course(client, author_token, category)
    draft = await create_course_or_fail(client, author_token, category, title="Draft only")

    own = await enroll(client, author_token, published["id"])
    assert own.status_code == 403
    assert own.json()["error"]["code"] == "own_course_enrollment_forbidden"

    missing = await enroll(client, learner_token, draft["id"])
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "course_not_found"

    anonymous = await client.post(
        "/api/v1/learning/enrollments",
        json={"course_id": published["id"]},
    )
    assert anonymous.status_code == 401

    invalid = await client.post(
        "/api/v1/learning/enrollments",
        json={"course_id": "not-a-uuid"},
        headers=bearer(learner_token),
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"


async def test_lesson_content_is_protected_and_outline_has_no_content(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    author_token, _ = await register_course_author(client, session_factory)
    learner_token, _ = await register_and_token(client, email="reader@example.com")
    other_token, _ = await register_and_token(client, email="other@example.com")
    category = await category_id(client)
    course = await create_published_course(client, author_token, category)
    lesson_id = course["modules"][0]["lessons"][0]["id"]

    anonymous_outline = await client.get(f"/api/v1/catalog/courses/{course['slug']}")
    assert anonymous_outline.status_code == 200
    assert "content" not in anonymous_outline.json()["modules"][0]["lessons"][0]

    denied = await get_learning_course(client, learner_token, course["slug"])
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "enrollment_required"

    denied_lesson = await client.get(
        f"/api/v1/learning/courses/{course['slug']}/lessons/{lesson_id}",
        headers=bearer(learner_token),
    )
    assert denied_lesson.status_code == 403

    enrollment = await enroll_or_fail(client, learner_token, course["id"])
    outline = await get_learning_course(client, learner_token, course["slug"])
    assert outline.status_code == 200, outline.text
    assert outline.headers["cache-control"] == "private, no-store"
    assert outline.json()["enrollment_id"] == enrollment["id"]
    outline_lesson = outline.json()["modules"][0]["lessons"][0]
    assert outline_lesson["state"] == "not_started"
    assert "content" not in outline_lesson

    content = await client.get(
        f"/api/v1/learning/courses/{course['slug']}/lessons/{lesson_id}",
        headers=bearer(learner_token),
    )
    assert content.status_code == 200, content.text
    assert content.headers["cache-control"] == "private, no-store"
    assert "# " in content.json()["content"]
    assert content.json()["state"] == "not_started"

    foreign = await client.get(
        f"/api/v1/learning/enrollments/{enrollment['id']}",
        headers=bearer(other_token),
    )
    assert foreign.status_code == 404
    assert foreign.json()["error"]["code"] == "enrollment_not_found"

    await client.delete(
        f"/api/v1/learning/enrollments/{enrollment['id']}",
        headers=bearer(learner_token),
    )
    after_cancel = await get_learning_course(client, learner_token, course["slug"])
    assert after_cancel.status_code == 403


async def test_unpublished_course_is_closed_but_enrollment_remains(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    author_token, _ = await register_course_author(client, session_factory)
    learner_token, _ = await register_and_token(client, email="unpub@example.com")
    category = await category_id(client)
    course = await create_published_course(client, author_token, category)
    lesson_id = course["modules"][0]["lessons"][0]["id"]
    enrollment = await enroll_or_fail(client, learner_token, course["id"])

    unpublish = await client.post(
        f"/api/v1/courses/{course['id']}/unpublish",
        headers=bearer(author_token),
    )
    assert unpublish.status_code == 200

    outline = await get_learning_course(client, learner_token, course["slug"])
    assert outline.status_code == 409
    assert outline.json()["error"]["code"] == "course_not_available"

    content = await client.get(
        f"/api/v1/learning/courses/{course['slug']}/lessons/{lesson_id}",
        headers=bearer(learner_token),
    )
    assert content.status_code == 409

    update = await set_lesson_state(
        client, learner_token, enrollment["id"], lesson_id, "in_progress"
    )
    assert update.status_code == 409

    still_there = await client.get(
        f"/api/v1/learning/enrollments/by-course/{course['id']}",
        headers=bearer(learner_token),
    )
    assert still_there.status_code == 200
    assert still_there.json()["enrolled"] is True

    republish = await client.post(
        f"/api/v1/courses/{course['id']}/publish",
        headers=bearer(author_token),
    )
    assert republish.status_code == 200
    assert (await get_learning_course(client, learner_token, course["slug"])).status_code == 200


async def test_three_state_progress_and_structural_reconciliation(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    author_token, _ = await register_course_author(client, session_factory)
    learner_token, _ = await register_and_token(client, email="progress@example.com")
    data = await _two_lesson_course(client, author_token)
    course = data["course"]
    first, second = data["lessons"]
    enrollment = await enroll_or_fail(client, learner_token, course["id"])

    started = await set_lesson_state(
        client, learner_token, enrollment["id"], first["id"], "in_progress"
    )
    assert started.status_code == 200, started.text
    assert started.json()["lesson"]["state"] == "in_progress"
    assert started.json()["lesson"]["started_at"] is not None
    assert started.json()["course_progress"]["progress_percent"] == 0

    completed = await set_lesson_state(
        client, learner_token, enrollment["id"], first["id"], "completed"
    )
    assert completed.json()["course_progress"]["completed_lessons"] == 1
    assert completed.json()["course_progress"]["progress_percent"] == 50

    repeated = await set_lesson_state(
        client, learner_token, enrollment["id"], first["id"], "completed"
    )
    assert repeated.status_code == 200
    assert repeated.json()["course_progress"]["progress_percent"] == 50

    history = await client.get(
        f"/api/v1/learning/enrollments/{enrollment['id']}/history",
        headers=bearer(learner_token),
    )
    assert history.status_code == 200
    completed_events = [
        event
        for event in history.json()["events"]
        if event["event_type"] == "lesson_completed"
        and event["lesson_id"] == first["id"]
    ]
    assert len(completed_events) == 1

    reopened_lesson = await set_lesson_state(
        client, learner_token, enrollment["id"], first["id"], "in_progress"
    )
    assert reopened_lesson.json()["course_progress"]["progress_percent"] == 0
    assert reopened_lesson.json()["lesson"]["completed_at"] is None

    await set_lesson_state(
        client, learner_token, enrollment["id"], first["id"], "completed"
    )
    finished = await set_lesson_state(
        client, learner_token, enrollment["id"], second["id"], "completed"
    )
    assert finished.json()["course_progress"]["is_completed"] is True
    assert finished.json()["course_progress"]["progress_percent"] == 100

    enrollment_after = await client.get(
        f"/api/v1/learning/enrollments/{enrollment['id']}",
        headers=bearer(learner_token),
    )
    assert enrollment_after.json()["completed_at"] is not None

    # The author adds a third lesson to the published course: 100% -> 66%,
    # and the completion marker must be cleared in the same transaction.
    third = await add_lesson(
        client,
        author_token,
        course["id"],
        data["module"]["id"],
        title="Third",
    )
    progress = await client.get(
        f"/api/v1/learning/enrollments/{enrollment['id']}/progress",
        headers=bearer(learner_token),
    )
    assert progress.status_code == 200
    assert progress.json()["progress_percent"] == 66
    assert progress.json()["is_completed"] is False
    assert progress.json()["completed_at"] is None

    history = await client.get(
        f"/api/v1/learning/enrollments/{enrollment['id']}/history",
        headers=bearer(learner_token),
    )
    assert any(
        event["event_type"] == "course_reopened"
        for event in history.json()["events"]
    )

    removed = await client.delete(
        f"/api/v1/courses/{course['id']}/modules/{data['module']['id']}/lessons/{third['id']}",
        headers=bearer(author_token),
    )
    assert removed.status_code == 204
    progress = await client.get(
        f"/api/v1/learning/enrollments/{enrollment['id']}/progress",
        headers=bearer(learner_token),
    )
    assert progress.json()["progress_percent"] == 100
    assert progress.json()["is_completed"] is True
    assert progress.json()["removed_lessons_count"] == 0


async def test_deleted_lessons_preserve_history_and_block_course_delete(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    author_token, _ = await register_course_author(client, session_factory)
    learner_token, _ = await register_and_token(client, email="history@example.com")
    data = await _two_lesson_course(client, author_token, title="History course")
    course = data["course"]
    first, second = data["lessons"]
    enrollment = await enroll_or_fail(client, learner_token, course["id"])

    for lesson in (first, second):
        response = await set_lesson_state(
            client, learner_token, enrollment["id"], lesson["id"], "completed"
        )
        assert response.status_code == 200, response.text

    deleted = await client.delete(
        f"/api/v1/courses/{course['id']}/modules/{data['module']['id']}/lessons/{second['id']}",
        headers=bearer(author_token),
    )
    assert deleted.status_code == 204

    progress = await client.get(
        f"/api/v1/learning/enrollments/{enrollment['id']}/progress",
        headers=bearer(learner_token),
    )
    body = progress.json()
    assert body["total_lessons"] == 1
    assert body["completed_lessons"] == 1
    assert body["removed_lessons_count"] == 1
    assert body["is_completed"] is True

    history = await client.get(
        f"/api/v1/learning/enrollments/{enrollment['id']}/history",
        headers=bearer(learner_token),
    )
    assert history.status_code == 200
    removed = history.json()["removed_lessons"]
    assert len(removed) == 1
    assert removed[0]["lesson_id_original"] == second["id"]
    assert removed[0]["lesson_title"] == "Second"
    assert removed[0]["state"] == "completed"

    # Deleting the whole module leaves no current lessons: completion reopens,
    # but both history snapshots remain.
    module_deleted = await client.delete(
        f"/api/v1/courses/{course['id']}/modules/{data['module']['id']}",
        headers=bearer(author_token),
    )
    assert module_deleted.status_code == 204

    progress = await client.get(
        f"/api/v1/learning/enrollments/{enrollment['id']}/progress",
        headers=bearer(learner_token),
    )
    body = progress.json()
    assert body["total_lessons"] == 0
    assert body["progress_percent"] == 0
    assert body["is_completed"] is False
    assert body["removed_lessons_count"] == 2

    forbidden_delete = await client.delete(
        f"/api/v1/courses/{course['id']}",
        headers=bearer(author_token),
    )
    assert forbidden_delete.status_code == 409
    assert forbidden_delete.json()["error"]["code"] == "course_has_enrollments"


async def test_cancellation_preserves_progress_and_history(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    author_token, _ = await register_course_author(client, session_factory)
    learner_token, _ = await register_and_token(client, email="resume@example.com")
    category = await category_id(client)
    course = await create_published_course(client, author_token, category)
    lesson_id = course["modules"][0]["lessons"][0]["id"]

    enrollment = await enroll_or_fail(client, learner_token, course["id"])
    completed = await set_lesson_state(
        client, learner_token, enrollment["id"], lesson_id, "completed"
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["course_progress"]["is_completed"] is True

    cancelled = await client.delete(
        f"/api/v1/learning/enrollments/{enrollment['id']}",
        headers=bearer(learner_token),
    )
    assert cancelled.status_code == 204

    status = await client.get(
        f"/api/v1/learning/enrollments/by-course/{course['id']}",
        headers=bearer(learner_token),
    )
    assert status.status_code == 200
    assert status.json()["enrolled"] is False
    cancelled_enrollment = status.json()["enrollment"]
    assert cancelled_enrollment["status"] == "cancelled"
    assert cancelled_enrollment["progress"]["progress_percent"] == 100
    assert cancelled_enrollment["progress"]["is_completed"] is True

    blocked = await get_learning_course(client, learner_token, course["slug"])
    assert blocked.status_code == 403

    resumed = await enroll(client, learner_token, course["id"])
    assert resumed.status_code == 200, resumed.text
    body = resumed.json()
    assert body["id"] == enrollment["id"]
    assert body["status"] == "active"
    assert body["progress"]["completed_lessons"] == 1
    assert body["progress"]["progress_percent"] == 100
    assert body["progress"]["is_completed"] is True
    assert body["completed_at"] is not None

    content = await client.get(
        f"/api/v1/learning/courses/{course['slug']}/lessons/{lesson_id}",
        headers=bearer(learner_token),
    )
    assert content.status_code == 200
    assert content.json()["state"] == "completed"

    history = await client.get(
        f"/api/v1/learning/enrollments/{enrollment['id']}/history",
        headers=bearer(learner_token),
    )
    types = [event["event_type"] for event in history.json()["events"]]
    assert "cancelled" in types
    assert "reactivated" in types


async def test_author_previews_draft_but_learning_api_stays_closed(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    author_token, _ = await register_course_author(client, session_factory)
    learner_token, _ = await register_and_token(client, email="preview@example.com")
    category = await category_id(client)
    draft = await create_course_or_fail(client, author_token, category, title="Draft preview")
    module = await add_module(client, author_token, draft["id"], title="Draft module")
    lesson = await add_lesson(
        client, author_token, draft["id"], module["id"], title="Draft lesson"
    )

    author_view = await client.get(
        f"/api/v1/courses/{draft['id']}",
        headers=bearer(author_token),
    )
    assert author_view.status_code == 200
    view_lesson = author_view.json()["modules"][0]["lessons"][0]
    assert view_lesson["id"] == lesson["id"]
    assert view_lesson["content"]

    learner_view = await client.get(
        f"/api/v1/courses/{draft['id']}",
        headers=bearer(learner_token),
    )
    assert learner_view.status_code == 404

    learner_learning = await get_learning_course(client, learner_token, draft["slug"])
    assert learner_learning.status_code == 404


async def test_admin_can_inspect_learning_without_own_enrollment(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    author_token, _ = await register_course_author(client, session_factory)
    learner_token, _ = await register_and_token(client, email="learner-admin@example.com")
    admin_token, _ = await register_admin(client, session_factory)
    category = await category_id(client)
    course = await create_published_course(client, author_token, category)
    lesson_id = course["modules"][0]["lessons"][0]["id"]
    enrollment = await enroll_or_fail(client, learner_token, course["id"])

    all_enrollments = await client.get(
        "/api/v1/learning/enrollments",
        headers=bearer(admin_token),
    )
    assert all_enrollments.status_code == 200
    assert all_enrollments.json()["total"] == 1

    foreign_detail = await client.get(
        f"/api/v1/learning/enrollments/{enrollment['id']}",
        headers=bearer(admin_token),
    )
    assert foreign_detail.status_code == 200

    foreign_progress = await client.get(
        f"/api/v1/learning/enrollments/{enrollment['id']}/progress",
        headers=bearer(admin_token),
    )
    assert foreign_progress.status_code == 200

    admin_outline = await get_learning_course(client, admin_token, course["slug"])
    assert admin_outline.status_code == 200, admin_outline.text
    assert admin_outline.json()["enrollment_id"] is None
    assert admin_outline.json()["progress"]["total_lessons"] == 1

    admin_content = await client.get(
        f"/api/v1/learning/courses/{course['slug']}/lessons/{lesson_id}",
        headers=bearer(admin_token),
    )
    assert admin_content.status_code == 200
    assert admin_content.json()["content"]

    learner_all = await client.get(
        "/api/v1/learning/enrollments",
        headers=bearer(learner_token),
    )
    assert learner_all.status_code == 403
    assert learner_all.json()["error"]["code"] == "insufficient_permissions"


async def test_rbac_guards_and_ownership(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    author_token, _ = await register_course_author(client, session_factory)
    owner_token, owner = await register_and_token(client, email="owner@example.com")
    other_token, _ = await register_and_token(client, email="intruder@example.com")
    category = await category_id(client)
    course = await create_published_course(client, author_token, category)
    enrollment = await enroll_or_fail(client, owner_token, course["id"])

    no_token = await client.get("/api/v1/learning/enrollments/mine")
    assert no_token.status_code == 401

    foreign = await client.get(
        f"/api/v1/learning/enrollments/{enrollment['id']}",
        headers=bearer(other_token),
    )
    assert foreign.status_code == 404

    await clear_roles(session_factory, owner["id"])
    forbidden = await client.get(
        "/api/v1/learning/enrollments/mine",
        headers=bearer(owner_token),
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "insufficient_permissions"


async def test_concurrent_enrollment_creates_one_row(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    author_token, _ = await register_course_author(client, session_factory)
    learner_token, _ = await register_and_token(client, email="race@example.com")
    category = await category_id(client)
    course = await create_published_course(client, author_token, category)

    first, second = await asyncio.gather(
        enroll(client, learner_token, course["id"]),
        enroll(client, learner_token, course["id"]),
    )
    statuses = sorted([first.status_code, second.status_code])
    assert statuses == [201, 409]
    loser = first if first.status_code == 409 else second
    assert loser.json()["error"]["code"] == "already_enrolled"


async def test_inactive_category_closes_learning(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    from tests.integration.helpers import set_category_active

    author_token, _ = await register_course_author(client, session_factory)
    learner_token, _ = await register_and_token(client, email="inactive@example.com")
    await set_category_active(session_factory, "programming", True)
    category = await category_id(client, "programming")
    course = await create_published_course(client, author_token, category)
    await enroll_or_fail(client, learner_token, course["id"])

    await set_category_active(session_factory, "programming", False)
    try:
        outline = await get_learning_course(client, learner_token, course["slug"])
        assert outline.status_code == 409
        assert outline.json()["error"]["code"] == "course_not_available"
    finally:
        await set_category_active(session_factory, "programming", True)
