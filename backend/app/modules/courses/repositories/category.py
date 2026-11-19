"""Persistence operations for course categories."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.courses.models.category import Category


class CategoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active(self) -> list[Category]:
        statement = (
            select(Category)
            .where(Category.is_active.is_(True))
            .order_by(Category.name.asc())
        )
        return list(await self._session.scalars(statement))

    async def get_by_id(self, category_id: uuid.UUID) -> Category | None:
        return await self._session.get(Category, category_id)

    async def get_by_slug(self, slug: str) -> Category | None:
        statement = select(Category).where(Category.slug == slug)
        return await self._session.scalar(statement)
