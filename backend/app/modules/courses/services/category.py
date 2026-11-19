"""Read-only category service (administration arrives in Sprint 8)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.courses.models.category import Category
from app.modules.courses.repositories.category import CategoryRepository


class CategoryService:
    def __init__(self, session: AsyncSession) -> None:
        self._categories = CategoryRepository(session)

    async def list_active(self) -> list[Category]:
        return await self._categories.list_active()
