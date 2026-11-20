"""Notification persistence, ownership and read state on PostgreSQL."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.events import register_event_handler
from app.modules.learning.models import LessonProgress
from tests.integration.helpers import (
    add_lesson, add_module, bearer, category_id, create_course_or_fail,
    register_and_token, register_course_author,
)

pytestmark = pytest.mark.integration


async def test_course_completion_notification_is_idempotent_and_private(client, session_factory):
    token, _learner = await register_and_token(client, email="notify-learner@example.com")
    author_token, _ = await register_course_author(client, session_factory, email="notify-author@example.com")
    course = await create_course_or_fail(client, author_token, await category_id(client), title="Уведомления Python")
    module = await add_module(client, author_token, course["id"])
    lesson = await add_lesson(client, author_token, course["id"], module["id"])
    assert (await client.post(f"/api/v1/courses/{course['id']}/publish", headers=bearer(author_token))).status_code == 200
    enrolled = await client.post("/api/v1/learning/enrollments", json={"course_id": course["id"]}, headers=bearer(token))
    assert enrolled.status_code == 201
    enrollment_id = enrolled.json()["id"]
    completed = await client.put(f"/api/v1/learning/enrollments/{enrollment_id}/lessons/{lesson['id']}/progress", json={"state": "completed"}, headers=bearer(token))
    assert completed.status_code == 200
    # Reading/reconciling progress repeatedly must not publish the transition again.
    progress_read = await client.get(f"/api/v1/learning/enrollments/{enrollment_id}/progress", headers=bearer(token))
    assert progress_read.status_code == 200, progress_read.text

    reopened = await client.put(f"/api/v1/learning/enrollments/{enrollment_id}/lessons/{lesson['id']}/progress", json={"state": "not_started"}, headers=bearer(token))
    assert reopened.status_code == 200
    completed_again = await client.put(f"/api/v1/learning/enrollments/{enrollment_id}/lessons/{lesson['id']}/progress", json={"state": "completed"}, headers=bearer(token))
    assert completed_again.status_code == 200
    progress_read = await client.get(f"/api/v1/learning/enrollments/{enrollment_id}/progress", headers=bearer(token))
    assert progress_read.status_code == 200, progress_read.text

    page = await client.get("/api/v1/notifications/me", headers=bearer(token))
    assert page.status_code == 200, page.text
    data = page.json()
    assert data["total"] == data["unread_count"] == 2
    item = data["items"][0]
    assert item["type"] == "course_completed"
    assert item["payload"]["enrollment_id"] == enrollment_id
    assert item["payload"]["course_slug"] == course["slug"]
    filtered = await client.get("/api/v1/notifications/me?page=2&page_size=1&unread_only=true", headers=bearer(token))
    assert filtered.status_code == 200
    assert filtered.json()["page"] == 2 and filtered.json()["total"] == 2 and len(filtered.json()["items"]) == 1

    other_token, _ = await register_and_token(client, email="notify-other@example.com")
    assert (await client.get("/api/v1/notifications/me", headers=bearer(other_token))).json()["total"] == 0
    foreign = await client.patch(f"/api/v1/notifications/{item['id']}/read", headers=bearer(other_token))
    assert foreign.status_code == 404
    assert (await client.get("/api/v1/notifications/me")).status_code == 401

    first = await client.patch(f"/api/v1/notifications/{item['id']}/read", headers=bearer(token))
    second = await client.patch(f"/api/v1/notifications/{item['id']}/read", headers=bearer(token))
    assert first.status_code == second.status_code == 200
    assert first.json()["read_at"] == second.json()["read_at"]
    assert (await client.get("/api/v1/notifications/unread-count", headers=bearer(token))).json()["unread_count"] == 1
    assert (await client.post("/api/v1/notifications/read-all", headers=bearer(token))).json()["updated"] == 1
    assert (await client.post("/api/v1/notifications/read-all", headers=bearer(token))).json()["updated"] == 0


async def test_notification_permission_is_required(client, session_factory):
    token, user = await register_and_token(client, email="notify-revoke@example.com")
    from tests.integration.helpers import clear_roles
    await clear_roles(session_factory, user["id"])
    response = await client.get("/api/v1/notifications/me", headers=bearer(token))
    assert response.status_code == 403, response.text


async def test_notification_failure_rolls_back_course_completion(client, session_factory):
    token, learner = await register_and_token(client, email="notify-rollback@example.com")
    author_token, _ = await register_course_author(client, session_factory, email="notify-rollback-author@example.com")
    course = await create_course_or_fail(client, author_token, await category_id(client), title="Atomic notifications")
    module = await add_module(client, author_token, course["id"])
    lesson = await add_lesson(client, author_token, course["id"], module["id"])
    await client.post(f"/api/v1/courses/{course['id']}/publish", headers=bearer(author_token))
    enrollment = await client.post("/api/v1/learning/enrollments", json={"course_id": course["id"]}, headers=bearer(token))
    assert enrollment.status_code == 201

    async def fail_after_notification(_session, _event):
        raise RuntimeError("injected notification handler failure")

    register_event_handler(fail_after_notification)
    try:
        with pytest.raises(RuntimeError, match="injected notification handler failure"):
            await client.put(
                f"/api/v1/learning/enrollments/{enrollment.json()['id']}/lessons/{lesson['id']}/progress",
                json={"state": "completed"}, headers=bearer(token),
            )
    finally:
        from app.core import events
        events._handlers.remove(fail_after_notification)

    async with session_factory() as session:
        progress = await session.scalar(select(LessonProgress).where(
            LessonProgress.enrollment_id == enrollment.json()["id"], LessonProgress.lesson_id == lesson["id"],
        ))
        assert progress is None
    assert (await client.get("/api/v1/notifications/me", headers=bearer(token))).json()["total"] == 0
