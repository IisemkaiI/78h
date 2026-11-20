"""Sprint 5 end-to-end assessment workflows on the dedicated PostgreSQL DB."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.assessments.models import AssignmentReview
from tests.integration.helpers import (
    assign_role, bearer, category_id, create_published_course, enroll_or_fail,
    register_and_token, register_course_author,
)

pytestmark = pytest.mark.integration


def _quiz_body(course: dict, *, answer: str = "a", required: bool = True) -> dict:
    lesson = course["modules"][0]["lessons"][0]
    return {
        "course_id": course["id"], "lesson_id": lesson["id"],
        "title": "Python basics quiz", "description": "Check the basics",
        "is_required": required, "passing_score_percent": 100,
        "time_limit_minutes": 20, "max_attempts": 3,
        "questions": [{
            "question_type": "single_choice", "prompt": "Select Python",
            "options": [{"id": "a", "text": "Python"}, {"id": "b", "text": "Ruby"}],
            "answer_key": answer, "points": 2, "position": 1,
            "explanation": "Python is the course language.",
        }],
    }


async def _publish(client: AsyncClient, path: str, token: str) -> dict:
    response = await client.post(path, headers=bearer(token))
    assert response.status_code == 200, response.text
    return response.json()


async def test_quiz_snapshot_grading_history_and_required_progress(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    author_token, _ = await register_course_author(client, session_factory, email="assessment-author@example.com")
    learner_token, _ = await register_and_token(client, email="assessment-learner@example.com")
    other_token, _ = await register_and_token(client, email="assessment-other@example.com")
    course = await create_published_course(client, author_token, await category_id(client))
    enrollment = await enroll_or_fail(client, learner_token, course["id"])

    created = await client.post("/api/v1/assessments/quizzes", json=_quiz_body(course), headers=bearer(author_token))
    assert created.status_code == 201, created.text
    quiz_id = created.json()["id"]
    await _publish(client, f"/api/v1/assessments/quizzes/{quiz_id}/publish", author_token)

    progress = await client.get(f"/api/v1/learning/enrollments/{enrollment['id']}/progress", headers=bearer(learner_token))
    assert progress.status_code == 200
    assert progress.json()["total_required_assessments"] == 1
    assert progress.json()["progress_percent"] == 0

    first = await client.post(f"/api/v1/assessments/quizzes/{quiz_id}/attempts", headers=bearer(learner_token))
    assert first.status_code == 201, first.text
    assert "answer_key" not in first.text and "explanation" not in first.text
    first_question = first.json()["questions"][0]["id"]
    foreign_answers = await client.put(
        f"/api/v1/assessments/attempts/{first.json()['id']}/answers",
        json=[{"question_id": first_question, "answer": "a"}], headers=bearer(other_token),
    )
    assert foreign_answers.status_code == 404
    await client.put(f"/api/v1/assessments/attempts/{first.json()['id']}/answers",
                     json=[{"question_id": first_question, "answer": "b"}], headers=bearer(learner_token))
    failed = await client.post(f"/api/v1/assessments/attempts/{first.json()['id']}/submit", headers=bearer(learner_token))
    assert failed.status_code == 200, failed.text
    assert failed.json()["passed"] is False
    assert failed.json()["score"] == 0
    failed_notice = await client.get("/api/v1/notifications/me", headers=bearer(learner_token))
    assert failed_notice.json()["items"][0]["type"] == "quiz_completed"
    assert failed_notice.json()["items"][0]["payload"]["passed"] is False
    assert failed_notice.json()["items"][0]["payload"]["score"] == "0"
    repeat = await client.post(f"/api/v1/assessments/attempts/{first.json()['id']}/submit", headers=bearer(learner_token))
    assert repeat.status_code == 409

    second = await client.post(f"/api/v1/assessments/quizzes/{quiz_id}/attempts", headers=bearer(learner_token))
    assert second.status_code == 201, second.text
    second_question = second.json()["questions"][0]["id"]
    edited = await client.patch(f"/api/v1/assessments/quizzes/{quiz_id}",
                                json={"questions": [{**created.json()["questions"][0], "answer_key": "b"}]},
                                headers=bearer(author_token))
    assert edited.status_code == 200, edited.text
    saved = await client.put(f"/api/v1/assessments/attempts/{second.json()['id']}/answers",
                             json=[{"question_id": second_question, "answer": "a"}], headers=bearer(learner_token))
    assert saved.status_code == 200
    passed = await client.post(f"/api/v1/assessments/attempts/{second.json()['id']}/submit", headers=bearer(learner_token))
    assert passed.status_code == 200, passed.text
    assert passed.json()["passed"] is True
    quiz_notices = await client.get("/api/v1/notifications/me", headers=bearer(learner_token))
    assert [item["payload"]["passed"] for item in quiz_notices.json()["items"] if item["type"] == "quiz_completed"] == [True, False]
    assert passed.json()["quiz_version"] == created.json()["version"]
    history = await client.get(f"/api/v1/assessments/quizzes/{quiz_id}/attempts/mine", headers=bearer(learner_token))
    assert history.status_code == 200 and len(history.json()) == 2
    assert history.json()[0]["answers"][0]["explanation"] == "Python is the course language."
    progress = await client.get(f"/api/v1/learning/enrollments/{enrollment['id']}/progress", headers=bearer(learner_token))
    assert progress.json()["completed_required_assessments"] == 1
    third = await client.post(f"/api/v1/assessments/quizzes/{quiz_id}/attempts", headers=bearer(learner_token))
    assert third.status_code == 201
    limited = await client.post(f"/api/v1/assessments/quizzes/{quiz_id}/attempts", headers=bearer(learner_token))
    assert limited.status_code == 409
    assert limited.json()["error"]["code"] == "attempt_limit_reached"
    archived = await client.post(f"/api/v1/assessments/quizzes/{quiz_id}/archive", headers=bearer(author_token))
    assert archived.status_code == 200
    after_archive = await client.get(f"/api/v1/learning/enrollments/{enrollment['id']}/progress", headers=bearer(learner_token))
    assert after_archive.json()["total_required_assessments"] == 0
    retained = await client.get(f"/api/v1/assessments/quizzes/{quiz_id}/attempts/mine", headers=bearer(learner_token))
    assert retained.status_code == 200 and len(retained.json()) == 3


async def test_assignment_review_revisions_teacher_scope_and_course_progress(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    author_token, _ = await register_course_author(client, session_factory, email="assignment-author@example.com")
    learner_token, learner = await register_and_token(client, email="assignment-learner@example.com")
    teacher_token, teacher = await register_and_token(client, email="assigned-teacher@example.com")
    foreign_token, _ = await register_and_token(client, email="foreign-teacher@example.com")
    await assign_role(session_factory, teacher["id"], "teacher")
    await assign_role(session_factory, (await client.get("/api/v1/auth/me", headers=bearer(foreign_token))).json()["id"], "teacher")
    course = await create_published_course(client, author_token, await category_id(client))
    enrollment = await enroll_or_fail(client, learner_token, course["id"])
    lesson_id = course["modules"][0]["lessons"][0]["id"]

    assignment = await client.post("/api/v1/assessments/assignments", json={
        "course_id": course["id"], "lesson_id": lesson_id, "title": "Write a function",
        "description": "Write a Python function.", "requirements": "Include a short explanation.",
        "max_points": 10, "allow_resubmission": True, "is_required": True,
    }, headers=bearer(author_token))
    assert assignment.status_code == 201, assignment.text
    assignment_id = assignment.json()["id"]
    await _publish(client, f"/api/v1/assessments/assignments/{assignment_id}/publish", author_token)

    assigned = await client.post(f"/api/v1/assessments/courses/{course['id']}/instructors",
                                 json={"instructor_id": teacher["id"]}, headers=bearer(author_token))
    assert assigned.status_code == 201, assigned.text
    denied = await client.get(f"/api/v1/assessments/courses/{course['id']}/assignments", headers=bearer(foreign_token))
    assert denied.status_code == 404

    draft = await client.put(f"/api/v1/assessments/assignments/{assignment_id}/submission/draft",
                             json={"response_text": "def greet(): return 'hello'"}, headers=bearer(learner_token))
    assert draft.status_code == 200, draft.text
    submitted = await client.post(f"/api/v1/assessments/assignments/{assignment_id}/submission/submit", headers=bearer(learner_token))
    assert submitted.status_code == 200 and submitted.json()["status"] == "submitted"

    queue = await client.get(f"/api/v1/assessments/assignments/{assignment_id}/submissions", headers=bearer(teacher_token))
    assert queue.status_code == 200 and len(queue.json()) == 1
    row_id = queue.json()[0]["id"]
    await client.post(f"/api/v1/assessments/submissions/{row_id}/start-review", headers=bearer(teacher_token))
    revision = await client.post(f"/api/v1/assessments/submissions/{row_id}/review",
                                 json={"decision": "revision_required", "score": 3, "comment": "Add an explanation."},
                                 headers=bearer(teacher_token))
    assert revision.status_code == 200 and revision.json()["status"] == "revision_required"
    assert revision.json()["is_accepted"] is False
    revision_notice = await client.get("/api/v1/notifications/me", headers=bearer(learner_token))
    assert revision_notice.json()["items"][0]["type"] == "assignment_revision_required"
    assert revision_notice.json()["items"][0]["payload"]["version"] == 1
    own = await client.get(f"/api/v1/assessments/assignments/{assignment_id}/submission/mine", headers=bearer(learner_token))
    assert own.status_code == 200 and own.json()["reviews"][0]["comment"] == "Add an explanation."
    incomplete = await client.get(f"/api/v1/learning/enrollments/{enrollment['id']}/progress", headers=bearer(learner_token))
    assert incomplete.json()["completed_required_assessments"] == 0

    await client.put(f"/api/v1/assessments/assignments/{assignment_id}/submission/draft",
                     json={"response_text": "def greet():\n    return 'hello'\n\nThis function greets."}, headers=bearer(learner_token))
    resubmitted = await client.post(f"/api/v1/assessments/assignments/{assignment_id}/submission/submit", headers=bearer(learner_token))
    assert resubmitted.status_code == 200 and resubmitted.json()["latest_version"] == 2
    await client.post(f"/api/v1/assessments/submissions/{row_id}/start-review", headers=bearer(teacher_token))
    accepted = await client.post(f"/api/v1/assessments/submissions/{row_id}/review",
                                 json={"decision": "accepted", "score": 9, "comment": "Good work."},
                                 headers=bearer(teacher_token))
    assert accepted.status_code == 200 and accepted.json()["is_accepted"] is True
    assert len(accepted.json()["versions"]) == 2
    assignment_notices = await client.get("/api/v1/notifications/me", headers=bearer(learner_token))
    assert [item["type"] for item in assignment_notices.json()["items"][:2]] == ["assignment_accepted", "assignment_revision_required"]
    assert assignment_notices.json()["items"][0]["payload"]["version"] == 2

    progress = await client.get(f"/api/v1/learning/enrollments/{enrollment['id']}/progress", headers=bearer(learner_token))
    assert progress.json()["completed_required_assessments"] == 1
    assert progress.json()["is_completed"] is False
    complete_lesson = await client.put(
        f"/api/v1/learning/enrollments/{enrollment['id']}/lessons/{lesson_id}/progress",
        json={"state": "completed"}, headers=bearer(learner_token),
    )
    assert complete_lesson.status_code == 200, complete_lesson.text
    assert complete_lesson.json()["course_progress"]["progress_percent"] == 100
    assert complete_lesson.json()["course_progress"]["is_completed"] is True

    removed = await client.delete(f"/api/v1/assessments/courses/{course['id']}/instructors/{teacher['id']}", headers=bearer(author_token))
    assert removed.status_code == 204
    inaccessible = await client.get(f"/api/v1/assessments/assignments/{assignment_id}/submissions", headers=bearer(teacher_token))
    assert inaccessible.status_code == 404
    async with session_factory() as session:
        reviews = list(await session.scalars(select(AssignmentReview).where(AssignmentReview.submission_id == row_id)))
        assert len(reviews) == 2


async def test_deleting_lesson_archives_and_detaches_assessments(
    client: AsyncClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    author_token, _ = await register_course_author(client, session_factory, email="lesson-delete-author@example.com")
    course = await create_published_course(client, author_token, await category_id(client))
    lesson_id = course["modules"][0]["lessons"][0]["id"]
    quiz = await client.post("/api/v1/assessments/quizzes", json=_quiz_body(course), headers=bearer(author_token))
    assert quiz.status_code == 201
    assignment = await client.post("/api/v1/assessments/assignments", json={
        "course_id": course["id"], "lesson_id": lesson_id,
        "title": "Delete lesson work", "description": "A practical task.", "max_points": 5,
    }, headers=bearer(author_token))
    assert assignment.status_code == 201
    removed = await client.delete(
        f"/api/v1/courses/{course['id']}/modules/{course['modules'][0]['id']}/lessons/{lesson_id}",
        headers=bearer(author_token),
    )
    assert removed.status_code == 204, removed.text
    loaded_quiz = await client.get(f"/api/v1/assessments/quizzes/{quiz.json()['id']}", headers=bearer(author_token))
    assert loaded_quiz.status_code == 200
    assert loaded_quiz.json()["status"] == "archived"
    assert loaded_quiz.json()["lesson_id"] is None
    loaded_assignments = await client.get(f"/api/v1/assessments/courses/{course['id']}/assignments", headers=bearer(author_token))
    assert loaded_assignments.status_code == 200
    assert loaded_assignments.json()[0]["status"] == "archived"
    assert loaded_assignments.json()[0]["lesson_id"] is None
