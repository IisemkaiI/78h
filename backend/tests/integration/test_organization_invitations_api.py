"""One-time organization invitations and membership acceptance on PostgreSQL."""
from __future__ import annotations

import asyncio
import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from app.modules.organizations.models import OrganizationInvitation, OrganizationMembership
from tests.integration.helpers import bearer, register_and_token

pytestmark = pytest.mark.integration


async def create_organization(client, token: str, name: str) -> dict:
    response = await client.post("/api/v1/organizations", json={
        "name": name, "slug": f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}"
    }, headers=bearer(token))
    assert response.status_code == 201, response.text
    return response.json()


async def invite(client, token: str, organization_id: str, email: str, role: str = "employee"):
    return await client.post(
        f"/api/v1/organizations/{organization_id}/invitations",
        json={"email": email, "role": role},
        headers=bearer(token),
    )


async def accept(client, token: str, invitation_token: str):
    return await client.post(
        "/api/v1/organizations/invitations/accept",
        json={"token": invitation_token},
        headers=bearer(token),
    )


async def test_create_invitation_normalizes_email_hashes_secret_and_expires_in_seven_days(
    client, session_factory
):
    owner_token, _ = await register_and_token(client, email="invite-create-owner@example.com")
    _target_token, target = await register_and_token(client, email="invite-target@example.com")
    organization = await create_organization(client, owner_token, "Invite Create")

    response = await invite(client, owner_token, organization["id"], "  INVITE-TARGET@Example.COM ")
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["email"] == "invite-target@example.com"
    assert data["role"] == "employee" and data["status"] == "pending"
    assert len(data["token"]) >= 40
    created_at = datetime.fromisoformat(data["created_at"])
    expires_at = datetime.fromisoformat(data["expires_at"])
    assert timedelta(days=7) - timedelta(seconds=2) <= expires_at - created_at <= timedelta(days=7) + timedelta(seconds=2)

    async with session_factory() as session:
        invitation = await session.get(OrganizationInvitation, data["id"])
        assert invitation is not None
        assert invitation.email_normalized == target["email"]
        assert invitation.token_hash == hashlib.sha256(data["token"].encode()).hexdigest()
        assert invitation.token_hash != data["token"]

    listed = await client.get(
        f"/api/v1/organizations/{organization['id']}/invitations", headers=bearer(owner_token)
    )
    assert listed.status_code == 200
    assert "token" not in listed.json()["items"][0]
    assert "token_hash" not in listed.json()["items"][0]


async def test_invitation_rbac_and_role_tampering(client, session_factory):
    owner_token, _ = await register_and_token(client, email="invite-rbac-owner@example.com")
    manager_token, manager = await register_and_token(client, email="invite-rbac-manager@example.com")
    scoped_admin_token, scoped_admin = await register_and_token(client, email="invite-rbac-admin@example.com")
    _employee_token, employee = await register_and_token(client, email="invite-rbac-employee@example.com")
    _manager_target_token, manager_target = await register_and_token(client, email="invite-rbac-manager-target@example.com")
    _admin_target_token, admin_target = await register_and_token(client, email="invite-rbac-admin-target@example.com")
    organization = await create_organization(client, owner_token, "Invite RBAC")

    async with session_factory() as session:
        session.add_all([
            OrganizationMembership(organization_id=uuid.UUID(organization["id"]), user_id=uuid.UUID(manager["id"]), role="manager", status="active"),
            OrganizationMembership(organization_id=uuid.UUID(organization["id"]), user_id=uuid.UUID(scoped_admin["id"]), role="admin", status="active"),
        ])
        await session.commit()

    manager_employee = await invite(client, manager_token, organization["id"], employee["email"], "employee")
    assert manager_employee.status_code == 201
    for role in ["manager", "admin"]:
        denied = await invite(client, manager_token, organization["id"], manager_target["email"], role)
        assert denied.status_code == 403, denied.text

    scoped_admin_manager = await invite(client, scoped_admin_token, organization["id"], manager_target["email"], "manager")
    assert scoped_admin_manager.status_code == 201
    scoped_admin_admin = await invite(client, scoped_admin_token, organization["id"], admin_target["email"], "admin")
    assert scoped_admin_admin.status_code == 403

    owner_admin = await invite(client, owner_token, organization["id"], admin_target["email"], "admin")
    assert owner_admin.status_code == 201
    owner_role_spoof = await invite(client, owner_token, organization["id"], admin_target["email"], "owner")
    assert owner_role_spoof.status_code == 422
    missing_account = await invite(client, owner_token, organization["id"], "not-registered@example.com")
    assert missing_account.status_code == 404


async def test_accept_requires_auth_matching_email_and_valid_token(client, session_factory):
    owner_token, _ = await register_and_token(client, email="invite-accept-owner@example.com")
    target_token, target = await register_and_token(client, email="invite-accept-target@example.com")
    other_token, _ = await register_and_token(client, email="invite-accept-other@example.com")
    organization = await create_organization(client, owner_token, "Invite Accept")
    created = await invite(client, owner_token, organization["id"], target["email"])
    invitation = created.json()

    mismatch = await accept(client, other_token, invitation["token"])
    assert mismatch.status_code == 403 and mismatch.json()["error"]["code"] == "invitation_email_mismatch"
    invalid = await accept(client, target_token, "x" * 43)
    assert invalid.status_code == 404
    unauthenticated = await client.post("/api/v1/organizations/invitations/accept", json={"token": invitation["token"]})
    assert unauthenticated.status_code == 401

    async with session_factory() as session:
        stored = await session.get(OrganizationInvitation, invitation["id"])
        assert stored is not None and stored.accepted_at is None


async def test_accept_creates_membership_once_and_token_cannot_be_reused(client, session_factory):
    owner_token, _ = await register_and_token(client, email="invite-once-owner@example.com")
    target_token, target = await register_and_token(client, email="invite-once-target@example.com")
    organization = await create_organization(client, owner_token, "Invite Once")
    created = await invite(client, owner_token, organization["id"], target["email"], "manager")
    invitation = created.json()

    accepted = await accept(client, target_token, invitation["token"])
    assert accepted.status_code == 200, accepted.text
    body = accepted.json()
    assert body["organization_id"] == organization["id"]
    assert body["role"] == "manager"
    replay = await accept(client, target_token, invitation["token"])
    assert replay.status_code == 409 and replay.json()["error"]["code"] == "invitation_already_accepted"

    async with session_factory() as session:
        memberships = (await session.scalars(select(OrganizationMembership).where(
            OrganizationMembership.organization_id == uuid.UUID(organization["id"]),
            OrganizationMembership.user_id == uuid.UUID(target["id"]),
            OrganizationMembership.status == "active",
        ))).all()
        stored = await session.get(OrganizationInvitation, invitation["id"])
        assert len(memberships) == 1
        assert stored is not None and stored.accepted_at is not None


async def test_expired_and_revoked_invitations_cannot_be_accepted(client, session_factory):
    owner_token, _ = await register_and_token(client, email="invite-expire-owner@example.com")
    expired_token, expired_user = await register_and_token(client, email="invite-expired-target@example.com")
    revoked_token, revoked_user = await register_and_token(client, email="invite-revoked-target@example.com")
    organization = await create_organization(client, owner_token, "Invite End States")
    expired = (await invite(client, owner_token, organization["id"], expired_user["email"])).json()
    revoked = (await invite(client, owner_token, organization["id"], revoked_user["email"])).json()

    async with session_factory() as session:
        await session.execute(update(OrganizationInvitation).where(
            OrganizationInvitation.id == uuid.UUID(expired["id"])
        ).values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))
        await session.commit()

    expired_response = await accept(client, expired_token, expired["token"])
    assert expired_response.status_code == 410 and expired_response.json()["error"]["code"] == "invitation_expired"
    revoked_response = await client.delete(
        f"/api/v1/organizations/{organization['id']}/invitations/{revoked['id']}", headers=bearer(owner_token)
    )
    assert revoked_response.status_code == 204
    accept_revoked = await accept(client, revoked_token, revoked["token"])
    assert accept_revoked.status_code == 409 and accept_revoked.json()["error"]["code"] == "invitation_revoked"
    revoke_again = await client.delete(
        f"/api/v1/organizations/{organization['id']}/invitations/{revoked['id']}", headers=bearer(owner_token)
    )
    assert revoke_again.status_code == 409


async def test_active_member_cannot_accept_invitation(client, session_factory):
    owner_token, _ = await register_and_token(client, email="invite-repeat-owner@example.com")
    target_token, target = await register_and_token(client, email="invite-repeat-target@example.com")
    organization = await create_organization(client, owner_token, "Invite Repeat")
    created = await invite(client, owner_token, organization["id"], target["email"])

    async with session_factory() as session:
        session.add(OrganizationMembership(
            organization_id=uuid.UUID(organization["id"]), user_id=uuid.UUID(target["id"]),
            role="employee", status="active",
        ))
        await session.commit()
    already_member = await accept(client, target_token, created.json()["token"])
    assert already_member.status_code == 409


async def test_removed_member_reactivates_through_new_invitation(client, session_factory):
    owner_token, _ = await register_and_token(client, email="invite-reactivate-owner@example.com")
    target_token, target = await register_and_token(client, email="invite-reactivate-target@example.com")
    organization = await create_organization(client, owner_token, "Invite Reactivate")
    membership_id = uuid.uuid4()
    async with session_factory() as session:
        session.add(OrganizationMembership(
            id=membership_id,
            organization_id=uuid.UUID(organization["id"]),
            user_id=uuid.UUID(target["id"]),
            role="employee",
            status="removed",
            ended_at=datetime.now(UTC) - timedelta(days=2),
        ))
        await session.commit()
    created = await invite(client, owner_token, organization["id"], target["email"], "manager")
    assert created.status_code == 201
    accepted = await accept(client, target_token, created.json()["token"])
    assert accepted.status_code == 200
    assert accepted.json()["membership_id"] == str(membership_id)
    assert accepted.json()["role"] == "manager"
    async with session_factory() as session:
        membership = await session.get(OrganizationMembership, membership_id)
        assert membership is not None and membership.status == "active" and membership.ended_at is None


async def test_concurrent_acceptance_consumes_invitation_once(client, session_factory):
    owner_token, _ = await register_and_token(client, email="invite-race-owner@example.com")
    target_token, target = await register_and_token(client, email="invite-race-target@example.com")
    organization = await create_organization(client, owner_token, "Invite Race")
    created = await invite(client, owner_token, organization["id"], target["email"])
    secret = created.json()["token"]

    first, second = await asyncio.gather(accept(client, target_token, secret), accept(client, target_token, secret))
    assert sorted([first.status_code, second.status_code]) == [200, 409]
    async with session_factory() as session:
        active_count = await session.scalar(select(OrganizationMembership.id).where(
            OrganizationMembership.organization_id == uuid.UUID(organization["id"]),
            OrganizationMembership.user_id == uuid.UUID(target["id"]),
            OrganizationMembership.status == "active",
        ))
        assert active_count is not None


async def test_concurrent_reissue_and_accept_do_not_deadlock(client, session_factory):
    owner_token, _ = await register_and_token(client, email="invite-reissue-race-owner@example.com")
    target_token, target = await register_and_token(client, email="invite-reissue-race-target@example.com")
    organization = await create_organization(client, owner_token, "Invite Reissue Race")
    first = await invite(client, owner_token, organization["id"], target["email"])
    accepted_first = await accept(client, target_token, first.json()["token"])
    assert accepted_first.status_code == 200
    membership_id = accepted_first.json()["membership_id"]
    removed = await client.delete(
        f"/api/v1/organizations/{organization['id']}/members/{membership_id}", headers=bearer(owner_token)
    )
    assert removed.status_code == 204
    second = await invite(client, owner_token, organization["id"], target["email"])
    assert second.status_code == 201

    issue_again, accept_again = await asyncio.gather(
        invite(client, owner_token, organization["id"], target["email"]),
        accept(client, target_token, second.json()["token"]),
    )
    assert issue_again.status_code == 409
    assert accept_again.status_code == 200


async def test_invitation_tenant_isolation_and_path_organization_wins(client, session_factory):
    owner_a_token, _ = await register_and_token(client, email="invite-tenant-a@example.com")
    owner_b_token, _ = await register_and_token(client, email="invite-tenant-b@example.com")
    _target_token, target = await register_and_token(client, email="invite-tenant-target@example.com")
    organization_a = await create_organization(client, owner_a_token, "Invite Tenant A")
    organization_b = await create_organization(client, owner_b_token, "Invite Tenant B")

    path_org_wins = await client.post(
        f"/api/v1/organizations/{organization_a['id']}/invitations",
        json={"email": target["email"], "role": "employee", "organization_id": organization_b["id"]},
        headers=bearer(owner_a_token),
    )
    assert path_org_wins.status_code == 201
    assert path_org_wins.json()["id"]
    listed_a = await client.get(f"/api/v1/organizations/{organization_a['id']}/invitations", headers=bearer(owner_a_token))
    listed_b = await client.get(f"/api/v1/organizations/{organization_b['id']}/invitations", headers=bearer(owner_b_token))
    assert [item["email"] for item in listed_a.json()["items"]] == [target["email"]]
    assert listed_b.json()["items"] == []

    foreign_list = await client.get(
        f"/api/v1/organizations/{organization_a['id']}/invitations", headers=bearer(owner_b_token)
    )
    assert foreign_list.status_code == 404
    foreign_revoke = await client.delete(
        f"/api/v1/organizations/{organization_b['id']}/invitations/{path_org_wins.json()['id']}",
        headers=bearer(owner_b_token),
    )
    assert foreign_revoke.status_code == 404


async def test_manager_sees_and_revokes_only_employee_invitations(client, session_factory):
    owner_token, _ = await register_and_token(client, email="invite-manager-scope-owner@example.com")
    manager_token, manager = await register_and_token(client, email="invite-manager-scope-manager@example.com")
    _employee_token, employee = await register_and_token(client, email="invite-manager-scope-employee@example.com")
    _manager_target_token, manager_target = await register_and_token(client, email="invite-manager-scope-target@example.com")
    organization = await create_organization(client, owner_token, "Invite Manager Scope")
    async with session_factory() as session:
        session.add(OrganizationMembership(
            organization_id=uuid.UUID(organization["id"]), user_id=uuid.UUID(manager["id"]),
            role="manager", status="active",
        ))
        await session.commit()

    employee_invite = await invite(client, manager_token, organization["id"], employee["email"])
    manager_invite = await invite(client, owner_token, organization["id"], manager_target["email"], "manager")
    assert employee_invite.status_code == manager_invite.status_code == 201
    visible = await client.get(f"/api/v1/organizations/{organization['id']}/invitations", headers=bearer(manager_token))
    assert visible.status_code == 200
    assert all(item["role"] == "employee" for item in visible.json()["items"])
    denied_revoke = await client.delete(
        f"/api/v1/organizations/{organization['id']}/invitations/{manager_invite.json()['id']}", headers=bearer(manager_token)
    )
    assert denied_revoke.status_code == 403
