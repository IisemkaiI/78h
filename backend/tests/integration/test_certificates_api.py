"""Certificate issuance, privacy and idempotency against real PostgreSQL."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.modules.certificates.models import Certificate
from app.modules.courses.models.course import Course
from app.modules.users.models import User
from tests.integration.helpers import (
    add_lesson,
    add_module,
    bearer,
    category_id,
    create_course_or_fail,
    create_published_course,
    enroll_or_fail,
    register_and_token,
    register_course_author,
)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def private_certificate_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "certificates_storage_dir", tmp_path / "certificates")


async def _completed_enrollment(client, session_factory, *, email="learner@example.com"):
    token, user = await register_and_token(client, email=email, display_name="Анна Смирнова")
    author_token, _ = await register_course_author(
        client, session_factory, email=f"author-{email}"
    )
    category = await category_id(client)
    course = await create_course_or_fail(
        client, author_token, category, title="Курс по Python"
    )
    module = await add_module(client, author_token, course["id"])
    lesson = await add_lesson(client, author_token, course["id"], module["id"])
    response = await client.post(f"/api/v1/courses/{course['id']}/publish", headers=bearer(author_token))
    assert response.status_code == 200, response.text
    enrolled = await client.post(
        "/api/v1/learning/enrollments", json={"course_id": course["id"]}, headers=bearer(token)
    )
    assert enrolled.status_code == 201, enrolled.text
    enrollment_id = enrolled.json()["id"]
    started = await client.put(
        f"/api/v1/learning/enrollments/{enrollment_id}/lessons/{lesson['id']}/progress",
        json={"state": "completed"}, headers=bearer(token),
    )
    assert started.status_code == 200, started.text
    return token, user, course, enrollment_id, lesson["id"]


async def test_issue_is_idempotent_private_and_publicly_verifiable(
    client, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    token, user, course, enrollment_id, _ = await _completed_enrollment(client, session_factory)
    first = await client.post(
        "/api/v1/certificates/issue", json={"enrollment_id": enrollment_id}, headers=bearer(token)
    )
    assert first.status_code == 201, first.text
    data = first.json()
    assert data["recipient_name"] == "Анна Смирнова"
    assert data["course_title"] == "Курс по Python"
    assert "pdf_storage_key" not in data

    second = await client.post(
        "/api/v1/certificates/issue", json={"enrollment_id": enrollment_id}, headers=bearer(token)
    )
    assert second.status_code == 201
    assert second.json()["id"] == data["id"]

    listing = await client.get("/api/v1/certificates/me", headers=bearer(token))
    assert listing.status_code == 200 and len(listing.json()) == 1
    downloaded = await client.get(
        f"/api/v1/certificates/{data['id']}/download", headers=bearer(token)
    )
    assert downloaded.status_code == 200
    assert downloaded.headers["content-type"] == "application/pdf"
    assert downloaded.content.startswith(b"%PDF-")

    public = await client.get(f"/api/v1/certificates/verify/{data['verification_code']}")
    assert public.status_code == 200
    public_data = public.json()
    assert public_data["valid"] is True
    assert set(public_data) == {"valid", "recipient_name", "course_title", "certificate_number", "issued_at"}
    assert user["email"] not in public.text
    assert user["id"] not in public.text
    assert course["id"] not in public.text

    # Course/profile edits after issuance must not alter the certificate snapshot.
    async with session_factory() as session:
        persisted = await session.scalar(select(Certificate).where(Certificate.id == data["id"]))
        loaded_user = await session.get(User, user["id"])
        loaded_course = await session.get(Course, course["id"])
        assert persisted is not None and loaded_user is not None and loaded_course is not None
        pdf_path = get_settings().certificates_storage_dir / persisted.pdf_storage_key
        loaded_user.display_name = "Новое имя"
        loaded_course.title = "Новое название"
        await session.commit()
    still_valid = await client.get(f"/api/v1/certificates/verify/{data['verification_code']}")
    assert still_valid.json()["recipient_name"] == "Анна Смирнова"
    assert still_valid.json()["course_title"] == "Курс по Python"

    # Reactivating the same enrollment still resolves to the original certificate.
    cancelled = await client.delete(
        f"/api/v1/learning/enrollments/{enrollment_id}", headers=bearer(token)
    )
    assert cancelled.status_code == 204
    reactivated = await client.post(
        "/api/v1/learning/enrollments", json={"course_id": course["id"]}, headers=bearer(token)
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["id"] == enrollment_id
    after_reactivation = await client.post(
        "/api/v1/certificates/issue", json={"enrollment_id": enrollment_id}, headers=bearer(token)
    )
    assert after_reactivation.json()["id"] == data["id"]

    second_token, _ = await register_and_token(client, email="another@example.com")
    foreign_pdf = await client.get(
        f"/api/v1/certificates/{data['id']}/download", headers=bearer(second_token)
    )
    assert foreign_pdf.status_code == 404

    invalid_code = await client.get("/api/v1/certificates/verify/not-a-real-code")
    assert invalid_code.status_code == 404
    anonymous_list = await client.get("/api/v1/certificates/me")
    assert anonymous_list.status_code == 401

    pdf_path.unlink()
    missing_pdf = await client.get(
        f"/api/v1/certificates/{data['id']}/download", headers=bearer(token)
    )
    assert missing_pdf.status_code == 404
    assert missing_pdf.json()["error"]["code"] == "certificate_file_missing"

    async with session_factory() as session:
        rows = list(await session.scalars(select(Certificate).where(Certificate.enrollment_id == enrollment_id)))
        assert len(rows) == 1


async def test_incomplete_course_cannot_receive_certificate(client, session_factory) -> None:
    token, _, _, enrollment_id, lesson_id = await _completed_enrollment(client, session_factory, email="incomplete@example.com")
    reset = await client.put(
        f"/api/v1/learning/enrollments/{enrollment_id}/lessons/{lesson_id}/progress",
        json={"state": "not_started"}, headers=bearer(token),
    )
    assert reset.status_code == 200, reset.text
    rejected = await client.post(
        "/api/v1/certificates/issue", json={"enrollment_id": enrollment_id}, headers=bearer(token)
    )
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "course_not_completed"


async def test_parallel_issue_requests_return_one_certificate(client, session_factory) -> None:
    token, _, _, enrollment_id, _ = await _completed_enrollment(client, session_factory, email="parallel@example.com")
    async def issue():
        return await client.post(
            "/api/v1/certificates/issue", json={"enrollment_id": enrollment_id}, headers=bearer(token)
        )
    responses = await asyncio.gather(issue(), issue())
    assert all(response.status_code == 201 for response in responses)
    assert responses[0].json()["id"] == responses[1].json()["id"]
    async with session_factory() as session:
        assert await session.scalar(select(Certificate.id).where(Certificate.enrollment_id == enrollment_id)) is not None


async def test_required_quiz_blocks_certificate_until_passed(client, session_factory) -> None:
    learner_token, _ = await register_and_token(client, email="quiz-cert-learner@example.com")
    author_token, _ = await register_course_author(
        client, session_factory, email="quiz-cert-author@example.com"
    )
    course = await create_published_course(client, author_token, await category_id(client))
    lesson_id = course["modules"][0]["lessons"][0]["id"]
    enrollment = await enroll_or_fail(client, learner_token, course["id"])
    completed = await client.put(
        f"/api/v1/learning/enrollments/{enrollment['id']}/lessons/{lesson_id}/progress",
        json={"state": "completed"}, headers=bearer(learner_token),
    )
    assert completed.status_code == 200
    quiz = await client.post("/api/v1/assessments/quizzes", json={
        "course_id": course["id"], "lesson_id": lesson_id, "title": "Required quiz",
        "description": "A required check", "is_required": True,
        "passing_score_percent": 100, "max_attempts": 2,
        "questions": [{
            "question_type": "single_choice", "prompt": "Pick Python",
            "options": [{"id": "py", "text": "Python"}, {"id": "js", "text": "JavaScript"}],
            "answer_key": "py", "points": 1, "position": 1,
        }],
    }, headers=bearer(author_token))
    assert quiz.status_code == 201, quiz.text
    quiz_id = quiz.json()["id"]
    published = await client.post(f"/api/v1/assessments/quizzes/{quiz_id}/publish", headers=bearer(author_token))
    assert published.status_code == 200
    blocked = await client.post(
        "/api/v1/certificates/issue", json={"enrollment_id": enrollment["id"]}, headers=bearer(learner_token)
    )
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "course_not_completed"

    attempt = await client.post(f"/api/v1/assessments/quizzes/{quiz_id}/attempts", headers=bearer(learner_token))
    question_id = attempt.json()["questions"][0]["id"]
    saved = await client.put(
        f"/api/v1/assessments/attempts/{attempt.json()['id']}/answers",
        json=[{"question_id": question_id, "answer": "py"}], headers=bearer(learner_token),
    )
    assert saved.status_code == 200
    passed = await client.post(f"/api/v1/assessments/attempts/{attempt.json()['id']}/submit", headers=bearer(learner_token))
    assert passed.status_code == 200 and passed.json()["passed"] is True
    issued = await client.post(
        "/api/v1/certificates/issue", json={"enrollment_id": enrollment["id"]}, headers=bearer(learner_token)
    )
    assert issued.status_code == 201, issued.text


async def test_required_assignment_blocks_certificate_until_accepted(client, session_factory) -> None:
    learner_token, _ = await register_and_token(client, email="task-cert-learner@example.com")
    author_token, _ = await register_course_author(
        client, session_factory, email="task-cert-author@example.com"
    )
    course = await create_published_course(client, author_token, await category_id(client))
    lesson_id = course["modules"][0]["lessons"][0]["id"]
    enrollment = await enroll_or_fail(client, learner_token, course["id"])
    completed = await client.put(
        f"/api/v1/learning/enrollments/{enrollment['id']}/lessons/{lesson_id}/progress",
        json={"state": "completed"}, headers=bearer(learner_token),
    )
    assert completed.status_code == 200
    assignment = await client.post("/api/v1/assessments/assignments", json={
        "course_id": course["id"], "lesson_id": lesson_id, "title": "Required practical",
        "description": "A required assignment", "requirements": "Submit a Python function.",
        "max_points": 10, "is_required": True, "allow_resubmission": True,
    }, headers=bearer(author_token))
    assert assignment.status_code == 201, assignment.text
    assignment_id = assignment.json()["id"]
    published = await client.post(
        f"/api/v1/assessments/assignments/{assignment_id}/publish", headers=bearer(author_token)
    )
    assert published.status_code == 200
    blocked = await client.post(
        "/api/v1/certificates/issue", json={"enrollment_id": enrollment["id"]}, headers=bearer(learner_token)
    )
    assert blocked.status_code == 409

    draft = await client.put(
        f"/api/v1/assessments/assignments/{assignment_id}/submission/draft",
        json={"response_text": "def total(a, b): return a + b"}, headers=bearer(learner_token),
    )
    assert draft.status_code == 200
    submitted = await client.post(
        f"/api/v1/assessments/assignments/{assignment_id}/submission/submit", headers=bearer(learner_token)
    )
    assert submitted.status_code == 200
    submission_id = submitted.json()["id"]
    started = await client.post(
        f"/api/v1/assessments/submissions/{submission_id}/start-review", headers=bearer(author_token)
    )
    assert started.status_code == 200
    accepted = await client.post(
        f"/api/v1/assessments/submissions/{submission_id}/review",
        json={"decision": "accepted", "score": 9, "comment": "Принято"},
        headers=bearer(author_token),
    )
    assert accepted.status_code == 200 and accepted.json()["is_accepted"] is True
    issued = await client.post(
        "/api/v1/certificates/issue", json={"enrollment_id": enrollment["id"]}, headers=bearer(learner_token)
    )
    assert issued.status_code == 201, issued.text
