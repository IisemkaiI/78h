"""Invitation creation, revocation and one-time membership acceptance."""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.core.security import normalize_email
from app.modules.organizations.models import Organization, OrganizationInvitation, OrganizationMembership
from app.modules.organizations.service import OrganizationService
from app.modules.users.models import User
from app.modules.users.rbac import PermissionCode

INVITATION_LIFETIME = timedelta(days=7)


def _new_token() -> str:
    """Return a URL-safe 256-bit bearer secret; only its SHA-256 digest is persisted."""
    return secrets.token_urlsafe(32)


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def invitation_status(invitation: OrganizationInvitation, now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    if invitation.accepted_at is not None:
        return "accepted"
    if invitation.expires_at <= now:
        return "expired"
    if invitation.revoked_at is not None:
        return "revoked"
    return "pending"


class OrganizationInvitationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.organizations = OrganizationService(session)

    @staticmethod
    def is_platform_admin(user: User) -> bool:
        return user.has_permissions(PermissionCode.ADMIN_MANAGE_PLATFORM)

    async def create(
        self,
        actor: User,
        organization_id: uuid.UUID,
        *,
        email: str,
        role: str,
    ) -> tuple[OrganizationInvitation, str]:
        organization, actor_membership = await self.organizations._lock_organization_and_authorize(
            actor, organization_id, "manage"
        )
        if organization.status != "active":
            raise ApiError(409, "organization_inactive", "Invitations cannot be created for an inactive organization.")
        if actor_membership is None:
            # The invitation audit FK intentionally requires an organization member as its issuer.
            raise ApiError(403, "organization_membership_required", "Join the organization before issuing invitations.")
        self._require_role_permission(actor, actor_membership, role)

        normalized_email = normalize_email(email)
        target_user = await self.session.scalar(select(User).where(User.email == normalized_email))
        if target_user is None or not target_user.is_active:
            raise ApiError(404, "invitee_not_found", "An active account with this email was not found.")

        now = datetime.now(UTC)
        # Lock invitation before membership in the same order used by accept(); this prevents
        # a create-versus-accept deadlock for an already removed member.
        previous = await self.session.scalar(select(OrganizationInvitation).where(
            OrganizationInvitation.organization_id == organization.id,
            OrganizationInvitation.email_normalized == normalized_email,
            OrganizationInvitation.accepted_at.is_(None),
            OrganizationInvitation.revoked_at.is_(None),
        ).with_for_update())
        if previous is not None:
            if previous.expires_at > now:
                raise ApiError(409, "invitation_already_pending", "An active invitation already exists for this email.")
            # Close expired open rows so the partial unique index permits a replacement.
            previous.revoked_at = now

        existing_membership = await self.session.scalar(select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization.id,
            OrganizationMembership.user_id == target_user.id,
        ).with_for_update())
        if existing_membership is not None and existing_membership.status != "removed":
            raise ApiError(409, "already_organization_member", "This account already belongs to the organization.")

        token = _new_token()
        invitation = OrganizationInvitation(
            organization_id=organization.id,
            invited_by_membership_id=actor_membership.id,
            email_normalized=normalized_email,
            role=role,
            token_hash=_token_digest(token),
            expires_at=now + INVITATION_LIFETIME,
        )
        self.session.add(invitation)
        try:
            await self.session.commit()
            await self.session.refresh(invitation)
        except IntegrityError as exc:
            await self.session.rollback()
            raise ApiError(409, "invitation_conflict", "A conflicting invitation already exists.") from exc
        return invitation, token

    async def list_for_organization(
        self, actor: User, organization_id: uuid.UUID
    ) -> list[OrganizationInvitation]:
        organization, membership = await self.organizations._lock_organization_and_authorize(
            actor, organization_id, "manage"
        )
        statement = select(OrganizationInvitation).where(
            OrganizationInvitation.organization_id == organization.id
        )
        if not self.is_platform_admin(actor) and membership and membership.role == "manager":
            statement = statement.where(OrganizationInvitation.role == "employee")
        statement = statement.order_by(OrganizationInvitation.created_at.desc(), OrganizationInvitation.id)
        return list((await self.session.scalars(statement)).all())

    async def revoke(self, actor: User, organization_id: uuid.UUID, invitation_id: uuid.UUID) -> None:
        organization, actor_membership = await self.organizations._lock_organization_and_authorize(
            actor, organization_id, "manage"
        )
        invitation = await self.session.scalar(select(OrganizationInvitation).where(
            OrganizationInvitation.id == invitation_id,
            OrganizationInvitation.organization_id == organization.id,
        ).with_for_update())
        if invitation is None:
            raise ApiError(404, "invitation_not_found", "Invitation not found.")
        if invitation.accepted_at is not None or invitation.revoked_at is not None or invitation.expires_at <= datetime.now(UTC):
            raise ApiError(409, "invitation_not_pending", "Only pending invitations can be revoked.")
        if actor_membership is None:
            raise ApiError(403, "organization_membership_required", "Join the organization before managing its invitations.")
        self._require_role_permission(actor, actor_membership, invitation.role)
        invitation.revoked_at = datetime.now(UTC)
        await self.session.commit()

    async def accept(self, actor: User, *, token: str) -> tuple[OrganizationInvitation, OrganizationMembership]:
        invitation = await self.session.scalar(select(OrganizationInvitation).where(
            OrganizationInvitation.token_hash == _token_digest(token)
        ).with_for_update())
        if invitation is None:
            raise ApiError(404, "invitation_not_found", "Invitation token is invalid.")
        if invitation.accepted_at is not None:
            raise ApiError(409, "invitation_already_accepted", "This invitation has already been used.")
        if invitation.revoked_at is not None:
            raise ApiError(409, "invitation_revoked", "This invitation has been revoked.")
        now = datetime.now(UTC)
        if invitation.expires_at <= now:
            raise ApiError(410, "invitation_expired", "This invitation has expired.")
        if normalize_email(actor.email) != invitation.email_normalized:
            raise ApiError(403, "invitation_email_mismatch", "This invitation belongs to a different account.")

        # The organization status is checked without taking its row lock; acceptance and revocation
        # serialize on the invitation row, while membership uniqueness remains enforced by PostgreSQL.
        organization = await self.session.get(Organization, invitation.organization_id)
        if organization is None or organization.status != "active":
            raise ApiError(409, "organization_inactive", "This invitation targets an inactive organization.")

        membership = await self.session.scalar(select(OrganizationMembership).where(
            OrganizationMembership.organization_id == invitation.organization_id,
            OrganizationMembership.user_id == actor.id,
        ).with_for_update())
        if membership is not None and membership.status != "removed":
            raise ApiError(409, "already_organization_member", "This account already belongs to the organization.")
        if membership is None:
            membership = OrganizationMembership(
                organization_id=invitation.organization_id,
                user_id=actor.id,
                role=invitation.role,
                status="active",
                joined_at=now,
            )
            self.session.add(membership)
        else:
            # A removed member can rejoin through a new invitation without duplicating the unique row.
            membership.role = invitation.role
            membership.status = "active"
            membership.joined_at = now
            membership.ended_at = None
        invitation.accepted_at = now
        try:
            await self.session.commit()
            await self.session.refresh(membership)
            await self.session.refresh(invitation)
        except IntegrityError as exc:
            await self.session.rollback()
            raise ApiError(409, "already_organization_member", "This account already belongs to the organization.") from exc
        return invitation, membership

    def _require_role_permission(self, actor: User, membership: OrganizationMembership, invited_role: str) -> None:
        if self.is_platform_admin(actor) or membership.role == "owner":
            return
        if membership.role == "admin" and invited_role in {"manager", "employee"}:
            return
        if membership.role == "manager" and invited_role == "employee":
            return
        raise ApiError(403, "organization_forbidden", "You cannot issue an invitation for this role.")
