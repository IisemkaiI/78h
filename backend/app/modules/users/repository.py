"""Data access for users and RBAC lookups.

The repository owns SQL only: no business rules, no HTTP concerns.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import normalize_email
from app.modules.users.models import Permission, Role, User


class UserRepository:
    """Persistence operations for :class:`User`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @staticmethod
    def _with_roles():
        """Eagerly load roles and their permissions (async-safe, no lazy IO)."""
        return selectinload(User.roles).selectinload(Role.permissions)

    async def get_by_id(self, user_id: uuid.UUID) -> User | None:
        statement = select(User).where(User.id == user_id).options(self._with_roles())
        return await self._session.scalar(statement)

    async def get_by_email(self, email: str) -> User | None:
        statement = (
            select(User).where(User.email == normalize_email(email)).options(self._with_roles())
        )
        return await self._session.scalar(statement)

    async def add(
        self,
        *,
        email: str,
        password_hash: str,
        display_name: str,
        roles: Sequence[Role],
    ) -> User:
        user = User(
            email=normalize_email(email),
            password_hash=password_hash,
            display_name=display_name,
            is_active=True,
        )
        user.roles = list(roles)
        self._session.add(user)
        await self._session.flush()
        return user

    async def get_role_by_code(self, code: str) -> Role | None:
        statement = (
            select(Role)
            .where(Role.code == code)
            .options(selectinload(Role.permissions))
        )
        return await self._session.scalar(statement)


class RbacRepository:
    """Read-only lookups for roles and permissions."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_roles_by_codes(self, codes: Sequence[str]) -> list[Role]:
        if not codes:
            return []
        statement = (
            select(Role)
            .where(Role.code.in_(list(codes)))
            .options(selectinload(Role.permissions))
        )
        return list(await self._session.scalars(statement))

    @staticmethod
    async def list_permissions_for_user(user: User) -> list[str]:
        """Union of permission codes across all roles of the user."""
        return user.permission_codes

    async def assign_roles(self, user: User, roles: Sequence[Role]) -> None:
        """Assign roles to a user. Used by admin tooling and tests, never by the API."""
        existing = {role.id for role in user.roles}
        for role in roles:
            if role.id not in existing:
                user.roles.append(role)
        await self._session.flush()

    async def list_permission_codes(self) -> list[str]:
        statement = select(Permission.code).order_by(Permission.code)
        return list(await self._session.scalars(statement))
