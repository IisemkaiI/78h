"""Organization-scoped department operations."""
from __future__ import annotations

import uuid

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.organizations.models import OrganizationDepartment, OrganizationMembership
from app.modules.organizations.service import OrganizationService
from app.modules.users.models import User


class OrganizationDepartmentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(self, actor: User, organization_id: uuid.UUID) -> list[tuple[OrganizationDepartment, int]]:
        _org, membership = await OrganizationService(self.session).get_authorized(actor, organization_id)
        if membership is None:
            raise ApiError(404, "organization_not_found", "Organization not found.")
        rows = await self.session.execute(
            select(OrganizationDepartment, func.count(OrganizationMembership.id))
            .outerjoin(OrganizationMembership, and_(
                OrganizationMembership.department_id == OrganizationDepartment.id,
                OrganizationMembership.status == "active",
            ))
            .where(OrganizationDepartment.organization_id == organization_id)
            .group_by(OrganizationDepartment.id)
            .order_by(OrganizationDepartment.name)
        )
        return list(rows.all())

    async def create(self, actor: User, organization_id: uuid.UUID, name: str) -> OrganizationDepartment:
        await self._require_manager(actor, organization_id, owners_admins_only=True)
        department = OrganizationDepartment(
            organization_id=organization_id, name=name.strip(), slug=f"dept-{uuid.uuid4().hex[:16]}"
        )
        self.session.add(department)
        await self.session.commit()
        await self.session.refresh(department)
        return department

    async def rename(self, actor: User, organization_id: uuid.UUID, department_id: uuid.UUID, name: str) -> OrganizationDepartment:
        await self._require_manager(actor, organization_id, owners_admins_only=True)
        department = await self._department(organization_id, department_id, lock=True)
        department.name = name.strip()
        await self.session.commit()
        await self.session.refresh(department)
        return department

    async def delete(self, actor: User, organization_id: uuid.UUID, department_id: uuid.UUID) -> None:
        await self._require_manager(actor, organization_id, owners_admins_only=True)
        department = await self._department(organization_id, department_id, lock=True)
        members = list((await self.session.scalars(select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.department_id == department_id,
        ).with_for_update())).all())
        for member in members:
            member.department_id = None
        await self.session.delete(department)
        await self.session.commit()

    async def set_member_department(
        self, actor: User, organization_id: uuid.UUID, membership_id: uuid.UUID, department_id: uuid.UUID | None
    ) -> OrganizationMembership:
        await self._require_manager(actor, organization_id)
        member = await self.session.scalar(select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.id == membership_id,
            OrganizationMembership.status == "active",
        ).with_for_update())
        if member is None:
            raise ApiError(404, "membership_not_found", "Active organization membership not found.")
        if department_id is not None:
            await self._department(organization_id, department_id)
        member.department_id = department_id
        await self.session.commit()
        await self.session.refresh(member)
        return member

    async def _department(self, organization_id: uuid.UUID, department_id: uuid.UUID, *, lock: bool = False) -> OrganizationDepartment:
        query = select(OrganizationDepartment).where(
            OrganizationDepartment.organization_id == organization_id,
            OrganizationDepartment.id == department_id,
        )
        if lock:
            query = query.with_for_update()
        department = await self.session.scalar(query)
        if department is None:
            raise ApiError(404, "department_not_found", "Department not found in this organization.")
        return department

    async def _require_manager(self, actor: User, organization_id: uuid.UUID, *, owners_admins_only: bool = False) -> None:
        _org, member = await OrganizationService(self.session)._lock_organization_and_authorize(
            actor, organization_id, "manage"
        )
        if member is None:
            raise ApiError(404, "organization_not_found", "Organization not found.")
        allowed = {"owner", "admin"} if owners_admins_only else {"owner", "admin", "manager"}
        if member.role not in allowed:
            raise ApiError(403, "organization_forbidden", "Insufficient organization role for this operation.")
