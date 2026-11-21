"""Organization lifecycle and organization-scoped authorization."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.organizations.models import Organization, OrganizationMembership
from app.modules.users.models import User
from app.modules.users.rbac import PermissionCode, RoleCode


class OrganizationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def is_platform_admin(user: User) -> bool:
        return user.has_permissions(PermissionCode.ADMIN_MANAGE_PLATFORM)

    async def create(self, actor: User, *, name: str, slug: str) -> Organization:
        organization = Organization(name=name, slug=slug, created_by_id=actor.id)
        self.session.add(organization)
        try:
            await self.session.flush()
            self.session.add(OrganizationMembership(
                organization_id=organization.id,
                user_id=actor.id,
                role="owner",
                status="active",
                joined_at=datetime.now(UTC),
            ))
            await self.session.commit()
            await self.session.refresh(organization)
            return organization
        except IntegrityError as exc:
            await self.session.rollback()
            raise ApiError(409, "organization_slug_conflict", "An organization with this slug already exists.") from exc

    async def list_for_user(self, actor: User) -> list[Organization]:
        statement = (
            select(Organization)
            .join(OrganizationMembership, OrganizationMembership.organization_id == Organization.id)
            .where(OrganizationMembership.user_id == actor.id, OrganizationMembership.status == "active")
            .order_by(Organization.created_at.desc())
        )
        return list((await self.session.scalars(statement)).all())

    async def get_authorized(self, actor: User, organization_id: uuid.UUID) -> tuple[Organization, OrganizationMembership | None]:
        organization = await self.session.get(Organization, organization_id)
        if organization is None:
            raise ApiError(404, "organization_not_found", "Organization not found.")
        membership = await self.get_membership(actor.id, organization_id)
        if membership is None and not self.is_platform_admin(actor):
            raise ApiError(404, "organization_not_found", "Organization not found.")
        return organization, membership

    async def get_membership(self, user_id: uuid.UUID, organization_id: uuid.UUID) -> OrganizationMembership | None:
        return await self.session.scalar(select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.status == "active",
        ))

    async def list_members(self, actor: User, organization_id: uuid.UUID) -> list[tuple[OrganizationMembership, User]]:
        organization, membership = await self.get_authorized(actor, organization_id)
        if not self.is_platform_admin(actor) and membership is None:
            raise ApiError(404, "organization_not_found", "Organization not found.")
        if not self.is_platform_admin(actor) and membership.role not in {"owner", "admin", "manager"}:
            raise ApiError(403, "organization_forbidden", "You cannot view this organization's member list.")
        statement = (
            select(OrganizationMembership, User)
            .join(User, User.id == OrganizationMembership.user_id)
            .where(OrganizationMembership.organization_id == organization.id, OrganizationMembership.status == "active")
            .order_by(OrganizationMembership.created_at, OrganizationMembership.id)
        )
        return list((await self.session.execute(statement)).all())

    async def update_role(self, actor: User, organization_id: uuid.UUID, member_id: uuid.UUID, role: str) -> OrganizationMembership:
        organization, actor_membership = await self._lock_organization_and_authorize(actor, organization_id, "manage")
        if member_id == (actor_membership.id if actor_membership else None):
            raise ApiError(403, "self_role_change_forbidden", "You cannot change your own organization role.")
        target = await self._active_member(organization.id, member_id, lock=True)
        target_user = await self.session.get(User, target.user_id)
        if target_user is None:  # Protected by FK; kept defensive for concurrent maintenance.
            raise ApiError(404, "membership_not_found", "Active membership not found.")
        self._require_manage_target(actor, actor_membership, target, target_user)
        if actor_membership and actor_membership.role == "manager" and role != "employee":
            raise ApiError(403, "organization_forbidden", "Managers cannot assign management roles.")
        if actor_membership and actor_membership.role == "admin" and (
            target.role not in {"manager", "employee"} or role in {"owner", "admin"}
        ):
            raise ApiError(403, "organization_forbidden", "Organization admins cannot change owner or admin roles.")
        if target.role == "owner" and role != "owner":
            await self._protect_last_owner(organization.id)
        target.role = role
        await self.session.commit()
        await self.session.refresh(target)
        return target

    async def remove_member(self, actor: User, organization_id: uuid.UUID, member_id: uuid.UUID) -> None:
        organization, actor_membership = await self._lock_organization_and_authorize(actor, organization_id, "manage")
        if member_id == (actor_membership.id if actor_membership else None):
            raise ApiError(400, "use_leave_organization", "Use the leave endpoint to remove your own membership.")
        target = await self._active_member(organization.id, member_id, lock=True)
        target_user = await self.session.get(User, target.user_id)
        if target_user is None:  # Protected by FK; kept defensive for concurrent maintenance.
            raise ApiError(404, "membership_not_found", "Active membership not found.")
        self._require_manage_target(actor, actor_membership, target, target_user)
        if target.role == "owner":
            await self._protect_last_owner(organization.id)
        target.status = "removed"
        target.ended_at = datetime.now(UTC)
        await self.session.commit()

    async def leave(self, actor: User, organization_id: uuid.UUID) -> None:
        organization, membership = await self._lock_organization_and_authorize(actor, organization_id, "member")
        if membership is None:
            raise ApiError(404, "membership_not_found", "Active membership not found.")
        membership = await self._active_member(organization.id, membership.id, lock=True)
        if membership.role == "owner":
            await self._protect_last_owner(organization.id)
        membership.status = "removed"
        membership.ended_at = datetime.now(UTC)
        await self.session.commit()

    async def _lock_organization_and_authorize(self, actor: User, organization_id: uuid.UUID, capability: str) -> tuple[Organization, OrganizationMembership | None]:
        organization = await self.session.scalar(select(Organization).where(Organization.id == organization_id).with_for_update())
        if organization is None:
            raise ApiError(404, "organization_not_found", "Organization not found.")
        membership = await self.get_membership(actor.id, organization_id)
        is_admin = self.is_platform_admin(actor)
        if membership is None and not is_admin:
            raise ApiError(404, "organization_not_found", "Organization not found.")
        if capability == "manage" and not is_admin:
            if membership is None or membership.role not in {"owner", "admin", "manager"}:
                raise ApiError(403, "organization_forbidden", "You cannot manage this organization's members.")
        return organization, membership

    async def _active_member(self, organization_id: uuid.UUID, member_id: uuid.UUID, *, lock: bool) -> OrganizationMembership:
        statement = select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.id == member_id,
            OrganizationMembership.status == "active",
        )
        if lock:
            statement = statement.with_for_update()
        membership = await self.session.scalar(statement)
        if membership is None:
            raise ApiError(404, "membership_not_found", "Active membership not found.")
        return membership

    def _require_manage_target(
        self,
        actor: User,
        actor_membership: OrganizationMembership | None,
        target: OrganizationMembership,
        target_user: User,
    ) -> None:
        if self.is_platform_admin(actor) or (actor_membership and actor_membership.role == "owner"):
            return
        if actor_membership and actor_membership.role == "admin" and target.role in {"manager", "employee"}:
            return
        if (
            actor_membership
            and actor_membership.role == "manager"
            and target.role == "employee"
            and not target_user.has_role(RoleCode.ADMIN)
        ):
            return
        raise ApiError(403, "organization_forbidden", "You cannot change this member's role or status.")

    async def _protect_last_owner(self, organization_id: uuid.UUID) -> None:
        owners = await self.session.scalar(select(func.count()).select_from(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.status == "active",
            OrganizationMembership.role == "owner",
        ))
        if (owners or 0) <= 1:
            raise ApiError(409, "last_owner_required", "The last active owner cannot be removed or demoted.")
