"""Minimal administration and organization departments on PostgreSQL."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.organizations.models import OrganizationCourseAssignment, OrganizationMembership
from app.modules.learning.models.enrollment import Enrollment
from app.workers.tasks import mark_overdue_assignments
from tests.integration.helpers import add_lesson, add_module, bearer, category_id, create_course_or_fail, register_and_token, register_with_role
from app.modules.users.rbac import RoleCode

pytestmark = pytest.mark.integration


async def _org(client, token: str, name: str):
    response = await client.post("/api/v1/organizations", json={"name": name, "slug": f"{name.lower()}-{uuid.uuid4().hex[:8]}"}, headers=bearer(token))
    assert response.status_code == 201, response.text
    return response.json()


async def test_department_lifecycle_and_tenant_isolation(client, session_factory):
    owner_token, _ = await register_and_token(client, email="dept-owner@example.com")
    employee_token, employee = await register_and_token(client, email="dept-employee@example.com")
    other_owner_token, _ = await register_and_token(client, email="dept-other-owner@example.com")
    first = await _org(client, owner_token, "DeptFirst")
    other = await _org(client, other_owner_token, "DeptOther")
    async with session_factory() as session:
        membership = OrganizationMembership(organization_id=uuid.UUID(first["id"]), user_id=uuid.UUID(employee["id"]), role="employee", status="active")
        session.add(membership)
        await session.commit()
        member_id = str(membership.id)
    created = await client.post(f"/api/v1/organizations/{first['id']}/departments", json={"name": "Разработка"}, headers=bearer(owner_token))
    assert created.status_code == 201, created.text
    department = created.json()
    cross_tenant = await client.patch(
        f"/api/v1/organizations/{first['id']}/members/{member_id}/department",
        json={"department_id": (await client.post(f"/api/v1/organizations/{other['id']}/departments", json={"name": "Другая"}, headers=bearer(other_owner_token))).json()["id"]},
        headers=bearer(owner_token),
    )
    assert cross_tenant.status_code == 404
    assigned = await client.patch(f"/api/v1/organizations/{first['id']}/members/{member_id}/department", json={"department_id": department["id"]}, headers=bearer(owner_token))
    assert assigned.status_code == 200 and assigned.json()["department_id"] == department["id"]
    listed = await client.get(f"/api/v1/organizations/{first['id']}/departments", headers=bearer(owner_token))
    assert listed.status_code == 200 and listed.json()[0]["members_count"] == 1
    renamed = await client.patch(f"/api/v1/organizations/{first['id']}/departments/{department['id']}", json={"name": "Продукт"}, headers=bearer(owner_token))
    assert renamed.status_code == 200 and renamed.json()["name"] == "Продукт"
    deleted = await client.delete(f"/api/v1/organizations/{first['id']}/departments/{department['id']}", headers=bearer(owner_token))
    assert deleted.status_code == 204


async def test_admin_api_requires_platform_permission_and_returns_real_overview(client, session_factory):
    token, _ = await register_and_token(client, email="admin-api-user@example.com")
    denied = await client.get("/api/v1/admin/overview", headers=bearer(token))
    assert denied.status_code == 403
    admin_token, _ = await register_with_role(client, session_factory, RoleCode.ADMIN, email="admin-api-admin@example.com")
    overview = await client.get("/api/v1/admin/overview", headers=bearer(admin_token))
    assert overview.status_code == 200, overview.text
    assert overview.json()["users_total"] >= 2
    users = await client.get("/api/v1/admin/users?q=admin-api-user", headers=bearer(admin_token))
    assert users.status_code == 200 and users.json()["total"] == 1
    organizations = await client.get("/api/v1/admin/organizations", headers=bearer(admin_token))
    assert organizations.status_code == 200


async def test_overdue_task_marks_past_due_incomplete_assignment_once(client, session_factory):
    admin_token, _ = await register_with_role(client, session_factory, RoleCode.ADMIN, email="overdue-platform-admin@example.com")
    author_token, _ = await register_with_role(client, session_factory, RoleCode.COURSE_AUTHOR, email="overdue-author@example.com")
    employee_token, employee = await register_and_token(client, email="overdue-employee@example.com")
    org = await _org(client, author_token, "OverdueOrg")
    course = await create_course_or_fail(client, author_token, await category_id(client), title=f"Overdue {uuid.uuid4().hex[:8]}")
    module = await add_module(client, author_token, course["id"])
    await add_lesson(client, author_token, course["id"], module["id"])
    published = await client.post(f"/api/v1/courses/{course['id']}/publish", headers=bearer(author_token))
    assert published.status_code == 200, published.text
    async with session_factory() as session:
        membership = OrganizationMembership(organization_id=uuid.UUID(org["id"]), user_id=uuid.UUID(employee["id"]), role="employee", status="active")
        session.add(membership)
        await session.commit()
        member_id = str(membership.id)
    created = await client.post(f"/api/v1/organizations/{org['id']}/assignments", json={
        "course_id": course["id"], "membership_ids": [member_id],
        "due_at": (datetime.now(UTC) - timedelta(days=2)).isoformat(),
    }, headers=bearer(author_token))
    assert created.status_code == 201, created.text
    accepted = await client.post(f"/api/v1/organizations/{org['id']}/assignments/{created.json()[0]['id']}/accept", headers=bearer(employee_token))
    assert accepted.status_code == 200, accepted.text
    report = await client.get("/api/v1/admin/overview", headers=bearer(admin_token))
    assert report.status_code == 200 and report.json()["assignments_accepted"] == 1
    async with session_factory() as session:
        marked = await mark_overdue_assignments(session)
    assert marked == 1
    async with session_factory() as session:
        row = await session.get(OrganizationCourseAssignment, uuid.UUID(created.json()[0]["id"]))
        assert row is not None and row.overdue_at is not None
        second_run = await mark_overdue_assignments(session)
        assert second_run == 0

