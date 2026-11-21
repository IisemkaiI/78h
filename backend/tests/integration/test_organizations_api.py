"""Organization lifecycle, scoped RBAC and isolation on real PostgreSQL."""
from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import select

from app.modules.organizations.models import OrganizationMembership
from tests.integration.helpers import bearer, register_and_token, register_with_role
from app.modules.users.rbac import RoleCode

pytestmark = pytest.mark.integration


async def create_org(client, token: str, suffix: str = "one") -> dict:
    response = await client.post("/api/v1/organizations", json={
        "name": f"Organization {suffix}", "slug": f"organization-{suffix}-{uuid.uuid4().hex[:8]}"
    }, headers=bearer(token))
    assert response.status_code == 201, response.text
    return response.json()


async def add_membership(session_factory, organization_id: str, user_id: str, role: str = "employee") -> str:
    membership_id = uuid.uuid4()
    async with session_factory() as session:
        session.add(OrganizationMembership(
            id=membership_id,
            organization_id=uuid.UUID(organization_id),
            user_id=uuid.UUID(user_id),
            role=role,
            status="active",
        ))
        await session.commit()
    return str(membership_id)


async def active_owner_count(session_factory, organization_id: str) -> int:
    async with session_factory() as session:
        return len((await session.scalars(select(OrganizationMembership).where(
            OrganizationMembership.organization_id == uuid.UUID(organization_id),
            OrganizationMembership.role == "owner",
            OrganizationMembership.status == "active",
        ))).all())


async def test_create_list_detail_and_owner_membership(client, session_factory):
    token, user = await register_and_token(client, email="org-create@example.com")
    organization = await create_org(client, token)
    assert organization["created_by_id"] == user["id"]

    listed = await client.get("/api/v1/organizations/me", headers=bearer(token))
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [organization["id"]]

    detail = await client.get(f"/api/v1/organizations/{organization['id']}", headers=bearer(token))
    assert detail.status_code == 200
    members = await client.get(f"/api/v1/organizations/{organization['id']}/members", headers=bearer(token))
    assert members.status_code == 200
    assert members.json()[0]["role"] == "owner"
    assert members.json()[0]["user_id"] == user["id"]


async def test_scoped_roles_and_self_privilege_escalation_protection(client, session_factory):
    owner_token, _ = await register_and_token(client, email="org-rbac-owner@example.com")
    employee_token, employee = await register_and_token(client, email="org-rbac-employee@example.com")
    manager_token, manager = await register_and_token(client, email="org-rbac-manager@example.com")
    organization = await create_org(client, owner_token, "rbac")
    employee_id = await add_membership(session_factory, organization["id"], employee["id"])
    manager_id = await add_membership(session_factory, organization["id"], manager["id"], "manager")

    self_promotion = await client.patch(
        f"/api/v1/organizations/{organization['id']}/members/{employee_id}",
        json={"role": "owner"}, headers=bearer(employee_token),
    )
    assert self_promotion.status_code == 403
    own_list = await client.get(f"/api/v1/organizations/{organization['id']}/members", headers=bearer(employee_token))
    assert own_list.status_code == 403

    manager_promotion = await client.patch(
        f"/api/v1/organizations/{organization['id']}/members/{employee_id}",
        json={"role": "manager"}, headers=bearer(manager_token),
    )
    assert manager_promotion.status_code == 403
    manager_change = await client.patch(
        f"/api/v1/organizations/{organization['id']}/members/{employee_id}",
        json={"role": "owner"}, headers=bearer(manager_token),
    )
    assert manager_change.status_code == 403

    promoted = await client.patch(
        f"/api/v1/organizations/{organization['id']}/members/{employee_id}",
        json={"role": "manager"}, headers=bearer(owner_token),
    )
    assert promoted.status_code == 200 and promoted.json()["role"] == "manager"
    promoted_owner = await client.patch(
        f"/api/v1/organizations/{organization['id']}/members/{manager_id}",
        json={"role": "owner"}, headers=bearer(owner_token),
    )
    assert promoted_owner.status_code == 200 and promoted_owner.json()["role"] == "owner"


async def test_last_owner_cannot_be_demoted_removed_or_leave(client, session_factory):
    owner_token, _owner = await register_and_token(client, email="org-last-owner@example.com")
    _second_owner_token, second_owner = await register_and_token(client, email="org-last-owner-target@example.com")
    admin_token, _admin = await register_with_role(
        client, session_factory, RoleCode.ADMIN, email="org-last-owner-admin@example.com"
    )
    organization = await create_org(client, owner_token, "last-owner")
    second_owner_id = await add_membership(session_factory, organization["id"], second_owner["id"], "owner")
    members = (await client.get(f"/api/v1/organizations/{organization['id']}/members", headers=bearer(owner_token))).json()
    owner_membership_id = members[0]["id"]

    demote_last = await client.patch(
        f"/api/v1/organizations/{organization['id']}/members/{second_owner_id}",
        json={"role": "employee"}, headers=bearer(owner_token),
    )
    # Demoting one of two owners is valid; the remaining owner stays protected.
    assert demote_last.status_code == 200
    remove_last = await client.delete(
        f"/api/v1/organizations/{organization['id']}/members/{owner_membership_id}", headers=bearer(admin_token),
    )
    demote = await client.patch(
        f"/api/v1/organizations/{organization['id']}/members/{owner_membership_id}",
        json={"role": "employee"}, headers=bearer(admin_token),
    )
    leave = await client.post(f"/api/v1/organizations/{organization['id']}/leave", headers=bearer(owner_token))
    assert remove_last.status_code == demote.status_code == leave.status_code == 409
    assert all(response.json()["error"]["code"] == "last_owner_required" for response in [remove_last, demote])
    assert leave.status_code == 409 and leave.json()["error"]["code"] == "last_owner_required"
    assert await active_owner_count(session_factory, organization["id"]) == 1


async def test_manager_can_remove_employee_and_removed_member_loses_access(client, session_factory):
    owner_token, _ = await register_and_token(client, email="org-remove-owner@example.com")
    manager_token, manager = await register_and_token(client, email="org-remove-manager@example.com")
    employee_token, employee = await register_and_token(client, email="org-remove-employee@example.com")
    organization = await create_org(client, owner_token, "remove-employee")
    manager_id = await add_membership(session_factory, organization["id"], manager["id"], "manager")
    employee_id = await add_membership(session_factory, organization["id"], employee["id"], "employee")

    removed = await client.delete(
        f"/api/v1/organizations/{organization['id']}/members/{employee_id}", headers=bearer(manager_token)
    )
    assert removed.status_code == 204
    assert (await client.get(f"/api/v1/organizations/{organization['id']}", headers=bearer(employee_token))).status_code == 404
    assert (await client.delete(
        f"/api/v1/organizations/{organization['id']}/members/{manager_id}", headers=bearer(owner_token)
    )).status_code == 204


async def test_manager_cannot_remove_owner_manager_or_platform_admin(client, session_factory):
    owner_token, _ = await register_and_token(client, email="org-protected-owner@example.com")
    manager_token, manager = await register_and_token(client, email="org-protected-manager@example.com")
    _employee_token, employee = await register_and_token(client, email="org-protected-employee@example.com")
    _other_owner_token, other_owner = await register_and_token(client, email="org-protected-other-owner@example.com")
    _scoped_admin_token, scoped_admin = await register_and_token(client, email="org-protected-scoped-admin@example.com")
    _second_manager_token, second_manager = await register_and_token(client, email="org-protected-second-manager@example.com")
    _platform_admin_token, platform_admin = await register_with_role(
        client, session_factory, RoleCode.ADMIN, email="org-protected-admin@example.com"
    )
    organization = await create_org(client, owner_token, "protected-roles")
    await add_membership(session_factory, organization["id"], manager["id"], "manager")
    await add_membership(session_factory, organization["id"], employee["id"], "employee")
    other_owner_id = await add_membership(session_factory, organization["id"], other_owner["id"], "owner")
    await add_membership(session_factory, organization["id"], second_manager["id"], "manager")
    scoped_admin_id = await add_membership(session_factory, organization["id"], scoped_admin["id"], "admin")
    admin_member_id = await add_membership(session_factory, organization["id"], platform_admin["id"], "employee")

    manager_list = await client.get(f"/api/v1/organizations/{organization['id']}/members", headers=bearer(manager_token))
    assert manager_list.status_code == 200
    manager_member_id = next(item["id"] for item in manager_list.json() if item["user_id"] == second_manager["id"])
    owner_member_id = next(item["id"] for item in manager_list.json() if item["user_id"] == other_owner["id"])
    manager_rows = {item["user_id"]: item for item in manager_list.json()}
    assert manager_rows[employee["id"]]["can_remove"] is True
    assert manager_rows[employee["id"]]["can_update_role"] is False
    assert manager_rows[platform_admin["id"]]["can_remove"] is False
    assert manager_rows[other_owner["id"]]["can_remove"] is False
    assert manager_rows[manager["id"]]["can_remove"] is False

    for membership_id in [owner_member_id, manager_member_id, other_owner_id, scoped_admin_id, admin_member_id]:
        response = await client.delete(
            f"/api/v1/organizations/{organization['id']}/members/{membership_id}", headers=bearer(manager_token)
        )
        assert response.status_code == 403, response.text


async def test_scoped_admin_can_manage_employees_but_not_owner_or_admin(client, session_factory):
    owner_token, _ = await register_and_token(client, email="org-scoped-admin-owner@example.com")
    scoped_admin_token, scoped_admin = await register_and_token(client, email="org-scoped-admin-actor@example.com")
    _other_admin_token, other_admin = await register_and_token(client, email="org-scoped-admin-target@example.com")
    _manager_token, manager = await register_and_token(client, email="org-scoped-admin-manager@example.com")
    _employee_token, employee = await register_and_token(client, email="org-scoped-admin-employee@example.com")
    organization = await create_org(client, owner_token, "scoped-admin")
    scoped_admin_id = await add_membership(session_factory, organization["id"], scoped_admin["id"], "admin")
    other_admin_id = await add_membership(session_factory, organization["id"], other_admin["id"], "admin")
    manager_id = await add_membership(session_factory, organization["id"], manager["id"], "manager")
    employee_id = await add_membership(session_factory, organization["id"], employee["id"], "employee")
    members_url = f"/api/v1/organizations/{organization['id']}/members"

    promote = await client.patch(f"{members_url}/{employee_id}", json={"role": "manager"}, headers=bearer(scoped_admin_token))
    assert promote.status_code == 200 and promote.json()["role"] == "manager"
    demote_manager = await client.patch(f"{members_url}/{manager_id}", json={"role": "employee"}, headers=bearer(scoped_admin_token))
    assert demote_manager.status_code == 200 and demote_manager.json()["role"] == "employee"
    remove_manager = await client.delete(f"{members_url}/{manager_id}", headers=bearer(scoped_admin_token))
    assert remove_manager.status_code == 204
    self_remove = await client.delete(f"{members_url}/{scoped_admin_id}", headers=bearer(scoped_admin_token))
    assert self_remove.status_code == 400
    other_admin_denied = await client.delete(f"{members_url}/{other_admin_id}", headers=bearer(scoped_admin_token))
    assert other_admin_denied.status_code == 403
    owner_id = next(item["id"] for item in (await client.get(members_url, headers=bearer(scoped_admin_token))).json() if item["role"] == "owner")
    owner_denied = await client.delete(f"{members_url}/{owner_id}", headers=bearer(scoped_admin_token))
    assert owner_denied.status_code == 403


async def test_two_owners_cannot_concurrently_remove_last_owner(client, session_factory):
    first_token, first = await register_and_token(client, email="org-race-first@example.com")
    second_token, second = await register_and_token(client, email="org-race-second@example.com")
    organization = await create_org(client, first_token, "owner-race")
    first_members = (await client.get(f"/api/v1/organizations/{organization['id']}/members", headers=bearer(first_token))).json()
    first_id = first_members[0]["id"]
    second_id = await add_membership(session_factory, organization["id"], second["id"], "owner")

    first_remove, second_remove = await asyncio.gather(
        client.delete(f"/api/v1/organizations/{organization['id']}/members/{second_id}", headers=bearer(first_token)),
        client.delete(f"/api/v1/organizations/{organization['id']}/members/{first_id}", headers=bearer(second_token)),
    )
    assert sorted([first_remove.status_code, second_remove.status_code]) == [204, 404]
    assert await active_owner_count(session_factory, organization["id"]) == 1


async def test_concurrent_leave_and_removal_preserve_an_owner(client, session_factory):
    first_token, first = await register_and_token(client, email="org-race-leave-first@example.com")
    second_token, second = await register_and_token(client, email="org-race-leave-second@example.com")
    organization = await create_org(client, first_token, "owner-leave-race")
    first_id = (await client.get(f"/api/v1/organizations/{organization['id']}/members", headers=bearer(first_token))).json()[0]["id"]
    await add_membership(session_factory, organization["id"], second["id"], "owner")

    leave, remove = await asyncio.gather(
        client.post(f"/api/v1/organizations/{organization['id']}/leave", headers=bearer(first_token)),
        client.delete(f"/api/v1/organizations/{organization['id']}/members/{first_id}", headers=bearer(second_token)),
    )
    assert sorted([leave.status_code, remove.status_code]) == [204, 404]
    assert await active_owner_count(session_factory, organization["id"]) == 1


async def test_concurrent_owner_role_demotion_preserves_an_owner(client, session_factory):
    first_token, first = await register_and_token(client, email="org-race-demote-first@example.com")
    second_token, second = await register_and_token(client, email="org-race-demote-second@example.com")
    organization = await create_org(client, first_token, "owner-demote-race")
    first_id = (await client.get(f"/api/v1/organizations/{organization['id']}/members", headers=bearer(first_token))).json()[0]["id"]
    second_id = await add_membership(session_factory, organization["id"], second["id"], "owner")

    demote_first, demote_second = await asyncio.gather(
        client.patch(f"/api/v1/organizations/{organization['id']}/members/{second_id}",
                     json={"role": "employee"}, headers=bearer(first_token)),
        client.patch(f"/api/v1/organizations/{organization['id']}/members/{first_id}",
                     json={"role": "employee"}, headers=bearer(second_token)),
    )
    assert sorted([demote_first.status_code, demote_second.status_code]) == [200, 403]
    assert await active_owner_count(session_factory, organization["id"]) == 1


async def test_tenant_isolation_and_foreign_membership_ids(client, session_factory):
    owner_a_token, owner_a = await register_and_token(client, email="org-tenant-a@example.com")
    owner_b_token, owner_b = await register_and_token(client, email="org-tenant-b@example.com")
    organization_a = await create_org(client, owner_a_token, "tenant-a")
    organization_b = await create_org(client, owner_b_token, "tenant-b")
    foreign_member_id = (await client.get(f"/api/v1/organizations/{organization_b['id']}/members", headers=bearer(owner_b_token))).json()[0]["id"]

    for method, path, kwargs in [
        (client.get, f"/api/v1/organizations/{organization_b['id']}", {}),
        (client.get, f"/api/v1/organizations/{organization_b['id']}/members", {}),
        (client.patch, f"/api/v1/organizations/{organization_a['id']}/members/{foreign_member_id}", {"json": {"role": "employee"}}),
        (client.delete, f"/api/v1/organizations/{organization_a['id']}/members/{foreign_member_id}", {}),
    ]:
        response = await method(path, headers=bearer(owner_a_token), **kwargs)
        assert response.status_code == 404, response.text

    outsider_token, _ = await register_and_token(client, email="org-tenant-outsider@example.com")
    no_membership = await client.get(f"/api/v1/organizations/{organization_a['id']}", headers=bearer(outsider_token))
    assert no_membership.status_code == 404
    assert (await client.get("/api/v1/organizations/me", headers=bearer(owner_a_token))).json()["items"][0]["id"] == organization_a["id"]
    assert (await client.get("/api/v1/organizations/me", headers=bearer(owner_b_token))).json()["items"][0]["id"] == organization_b["id"]
    assert (await client.get("/api/v1/organizations/me", headers=bearer(outsider_token))).json()["items"] == []
    assert (await client.get(f"/api/v1/organizations/{organization_a['id']}", headers=bearer(owner_b_token))).status_code == 404
    assert owner_a["id"] != owner_b["id"]


async def test_nonexistent_organization_and_membership_return_not_found(client, session_factory):
    owner_token, _ = await register_and_token(client, email="org-not-found-owner@example.com")
    organization = await create_org(client, owner_token, "not-found")
    missing_org = str(uuid.uuid4())
    missing_membership = str(uuid.uuid4())

    for response in [
        await client.get(f"/api/v1/organizations/{missing_org}", headers=bearer(owner_token)),
        await client.get(f"/api/v1/organizations/{missing_org}/members", headers=bearer(owner_token)),
        await client.patch(f"/api/v1/organizations/{missing_org}/members/{missing_membership}",
                           json={"role": "employee"}, headers=bearer(owner_token)),
        await client.delete(f"/api/v1/organizations/{missing_org}/members/{missing_membership}", headers=bearer(owner_token)),
        await client.patch(f"/api/v1/organizations/{organization['id']}/members/{missing_membership}",
                           json={"role": "employee"}, headers=bearer(owner_token)),
        await client.delete(f"/api/v1/organizations/{organization['id']}/members/{missing_membership}", headers=bearer(owner_token)),
        await client.post(f"/api/v1/organizations/{missing_org}/leave", headers=bearer(owner_token)),
        await client.post(f"/api/v1/organizations/{organization['id']}/leave",
                          headers=bearer((await register_and_token(client, email="org-no-membership-leave@example.com"))[0])),
    ]:
        assert response.status_code == 404, response.text


async def test_global_organization_manager_does_not_grant_scoped_access(client, session_factory):
    owner_token, _ = await register_and_token(client, email="org-global-owner@example.com")
    scoped_manager_token, _ = await register_with_role(
        client, session_factory, RoleCode.ORGANIZATION_MANAGER, email="org-global-role@example.com"
    )
    organization = await create_org(client, owner_token, "global-role")
    response = await client.get(f"/api/v1/organizations/{organization['id']}/members", headers=bearer(scoped_manager_token))
    assert response.status_code == 404


async def test_platform_admin_is_an_explicit_exception(client, session_factory):
    admin_token, admin_user = await register_with_role(
        client, session_factory, RoleCode.ADMIN, email="org-platform-admin@example.com"
    )
    owner_token, _ = await register_and_token(client, email="org-admin-target@example.com")
    organization = await create_org(client, owner_token, "admin-exception")
    response = await client.get(f"/api/v1/organizations/{organization['id']}/members", headers=bearer(admin_token))
    assert response.status_code == 200

    # A role label alone is insufficient; the specific platform-management permission gates the exception.
    from sqlalchemy import delete, insert
    from app.modules.users.models import Permission, Role, role_permissions

    async with session_factory() as session:
        admin_role_id = await session.scalar(select(Role.id).where(Role.code == RoleCode.ADMIN))
        platform_permission_id = await session.scalar(select(Permission.id).where(Permission.code == "admin:manage_platform"))
        await session.execute(delete(role_permissions).where(
            role_permissions.c.role_id == admin_role_id,
            role_permissions.c.permission_id == platform_permission_id,
        ))
        await session.commit()
    try:
        denied = await client.get(f"/api/v1/organizations/{organization['id']}/members", headers=bearer(admin_token))
        assert denied.status_code == 404
    finally:
        async with session_factory() as session:
            await session.execute(insert(role_permissions).values(
                role_id=admin_role_id, permission_id=platform_permission_id,
            ))
            await session.commit()
    assert admin_user["id"]
