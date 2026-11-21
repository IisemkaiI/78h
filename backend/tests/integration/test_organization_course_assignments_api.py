"""Corporate assignments and their learning integration on PostgreSQL."""
from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import select

from app.modules.organizations.models import OrganizationMembership, OrganizationCourseAssignment
from app.modules.learning.models.enrollment import Enrollment
from tests.integration.helpers import (
    add_lesson,
    add_module,
    bearer,
    category_id,
    create_course_or_fail,
    register_and_token,
    register_with_role,
)
from app.modules.users.rbac import RoleCode

pytestmark = pytest.mark.integration


async def _organization(client, token: str) -> dict:
    response = await client.post("/api/v1/organizations", json={
        "name": "Corporate Learning", "slug": f"corp-learning-{uuid.uuid4().hex[:10]}"
    }, headers=bearer(token))
    assert response.status_code == 201, response.text
    return response.json()


async def _membership(session_factory, org_id: str, user_id: str) -> str:
    membership_id = uuid.uuid4()
    async with session_factory() as session:
        session.add(OrganizationMembership(
            id=membership_id, organization_id=uuid.UUID(org_id),
            user_id=uuid.UUID(user_id), role="employee", status="active",
        ))
        await session.commit()
    return str(membership_id)


async def _published_course(client, token: str) -> dict:
    course = await create_course_or_fail(client, token, await category_id(client),
        title=f"Corporate Python {uuid.uuid4().hex[:8]}")
    module = await add_module(client, token, course["id"])
    lesson = await add_lesson(client, token, course["id"], module["id"])
    published = await client.post(f"/api/v1/courses/{course['id']}/publish", headers=bearer(token))
    assert published.status_code == 200, published.text
    return {**published.json(), "lesson_id": lesson["id"]}


async def test_bulk_assignment_acceptance_progress_and_archive_continuation(
    client, session_factory,
):
    author_token, author = await register_with_role(
        client, session_factory, RoleCode.COURSE_AUTHOR, email="corp-course-author@example.com"
    )
    employee_token, employee = await register_and_token(client, email="corp-learner@example.com")
    later_employee_token, later_employee = await register_and_token(client, email="corp-later-learner@example.com")
    org = await _organization(client, author_token)
    membership_id = await _membership(session_factory, org["id"], employee["id"])
    later_membership_id = await _membership(session_factory, org["id"], later_employee["id"])
    course = await _published_course(client, author_token)

    created = await client.post(f"/api/v1/organizations/{org['id']}/assignments", json={
        "course_id": course["id"], "membership_ids": [membership_id], "is_required": True,
    }, headers=bearer(author_token))
    assert created.status_code == 201, created.text
    assignment = created.json()[0]
    assert assignment["status"] == "pending"
    assert assignment["enrollment_id"] is None

    duplicate = await client.post(f"/api/v1/organizations/{org['id']}/assignments", json={
        "course_id": course["id"], "membership_ids": [membership_id],
    }, headers=bearer(author_token))
    assert duplicate.status_code == 409

    hidden = await client.get(f"/api/v1/organizations/{org['id']}/assignments", headers=bearer(employee_token))
    assert hidden.status_code == 200 and len(hidden.json()["items"]) == 1
    accept_url = f"/api/v1/organizations/{org['id']}/assignments/{assignment['id']}/accept"
    accept_responses = await asyncio.gather(*[
        client.post(accept_url, headers=bearer(employee_token)) for _ in range(2)
    ])
    assert sorted(response.status_code for response in accept_responses) == [200, 409]
    accepted = next(response for response in accept_responses if response.status_code == 200)
    assert accepted.status_code == 200, accepted.text
    body = accepted.json()
    assert body["status"] == "accepted" and body["enrollment_status"] == "active"
    enrollment_id = body["enrollment_id"]

    archived = await client.post(f"/api/v1/courses/{course['id']}/archive", headers=bearer(author_token))
    assert archived.status_code == 200, archived.text
    archived_assignment = await client.post(f"/api/v1/organizations/{org['id']}/assignments", json={
        "course_id": course["id"], "membership_ids": [later_membership_id],
    }, headers=bearer(author_token))
    assert archived_assignment.status_code == 409
    new_enrollment = await client.post("/api/v1/learning/enrollments", json={
        "course_id": course["id"],
    }, headers=bearer(later_employee_token))
    assert new_enrollment.status_code == 404
    learning = await client.get(f"/api/v1/learning/courses/{course['slug']}", headers=bearer(employee_token))
    assert learning.status_code == 200, learning.text
    lesson_content = await client.get(
        f"/api/v1/learning/courses/{course['slug']}/lessons/{course['lesson_id']}",
        headers=bearer(employee_token),
    )
    assert lesson_content.status_code == 200, lesson_content.text
    progress = await client.put(
        f"/api/v1/learning/enrollments/{enrollment_id}/lessons/{course['lesson_id']}/progress",
        json={"state": "completed"}, headers=bearer(employee_token),
    )
    assert progress.status_code == 200, progress.text
    assert progress.json()["course_progress"]["progress_percent"] == 100

    cancelled = await client.delete(
        f"/api/v1/learning/enrollments/{enrollment_id}", headers=bearer(employee_token)
    )
    assert cancelled.status_code == 204
    assignment_list = await client.get(
        f"/api/v1/organizations/{org['id']}/assignments", headers=bearer(employee_token)
    )
    assert assignment_list.status_code == 200
    learner_assignment = assignment_list.json()["items"][0]
    assert learner_assignment["status"] == "accepted"
    assert learner_assignment["enrollment_status"] == "cancelled"

    reactivated = await client.post("/api/v1/learning/enrollments", json={
        "course_id": course["id"],
    }, headers=bearer(employee_token))
    assert reactivated.status_code == 200, reactivated.text
    assert reactivated.json()["id"] == enrollment_id
    assert reactivated.json()["progress"]["progress_percent"] == 100

    stats = await client.get(f"/api/v1/organizations/{org['id']}/learning-stats", headers=bearer(author_token))
    assert stats.status_code == 200, stats.text
    assert stats.json()["accepted"] == 1 and stats.json()["completed_enrollments"] == 1
    async with session_factory() as session:
        enrollment = await session.get(Enrollment, uuid.UUID(enrollment_id))
        row = await session.get(OrganizationCourseAssignment, uuid.UUID(assignment["id"]))
        assert enrollment is not None and row is not None
        assert row.enrollment_id == enrollment.id and row.status == "accepted"
        assert enrollment.status == "active"
        assert enrollment.completed_at is not None


async def test_assignment_tenant_and_target_role_boundaries(client, session_factory):
    owner_token, _ = await register_with_role(
        client, session_factory, RoleCode.COURSE_AUTHOR, email="corp-scope-owner@example.com"
    )
    employee_token, employee = await register_and_token(client, email="corp-scope-employee@example.com")
    other_owner_token, _ = await register_and_token(client, email="corp-scope-other@example.com")
    org = await _organization(client, owner_token)
    other_org = await _organization(client, other_owner_token)
    employee_membership = await _membership(session_factory, org["id"], employee["id"])
    manager = await register_and_token(client, email="corp-scope-manager@example.com")
    manager_membership = uuid.uuid4()
    async with session_factory() as session:
        session.add(OrganizationMembership(
            id=manager_membership, organization_id=uuid.UUID(org["id"]),
            user_id=uuid.UUID(manager[1]["id"]), role="manager", status="active",
        ))
        await session.commit()
    course = await _published_course(client, owner_token)

    cross_tenant = await client.post(f"/api/v1/organizations/{org['id']}/assignments", json={
        "course_id": course["id"], "membership_ids": ["00000000-0000-0000-0000-000000000001"],
    }, headers=bearer(owner_token))
    assert cross_tenant.status_code == 404

    manager_target = await client.post(f"/api/v1/organizations/{org['id']}/assignments", json={
        "course_id": course["id"], "membership_ids": [str(manager_membership)],
    }, headers=bearer(owner_token))
    assert manager_target.status_code == 403

    manager_assign = await client.post(f"/api/v1/organizations/{org['id']}/assignments", json={
        "course_id": course["id"], "membership_ids": [employee_membership],
    }, headers=bearer(manager[0]))
    assert manager_assign.status_code == 201, manager_assign.text
    manager_cancel = await client.delete(
        f"/api/v1/organizations/{org['id']}/assignments/{manager_assign.json()[0]['id']}",
        headers=bearer(manager[0]),
    )
    assert manager_cancel.status_code == 204

    assigned = await client.post(f"/api/v1/organizations/{org['id']}/assignments", json={
        "course_id": course["id"], "membership_ids": [employee_membership],
    }, headers=bearer(owner_token))
    assert assigned.status_code == 201, assigned.text
    assignment_id = assigned.json()[0]["id"]
    foreign_accept = await client.post(
        f"/api/v1/organizations/{other_org['id']}/assignments/{assignment_id}/accept",
        headers=bearer(employee_token),
    )
    assert foreign_accept.status_code == 404
    foreign_list = await client.get(f"/api/v1/organizations/{org['id']}/assignments", headers=bearer(other_owner_token))
    assert foreign_list.status_code == 404

    cancelled = await client.delete(
        f"/api/v1/organizations/{org['id']}/assignments/{assignment_id}",
        headers=bearer(owner_token),
    )
    assert cancelled.status_code == 204
    cannot_accept = await client.post(
        f"/api/v1/organizations/{org['id']}/assignments/{assignment_id}/accept",
        headers=bearer(employee_token),
    )
    assert cannot_accept.status_code == 409
    async with session_factory() as session:
        record = await session.get(OrganizationCourseAssignment, uuid.UUID(assignment_id))
        assert record is not None and record.status == "cancelled" and record.enrollment_id is None
