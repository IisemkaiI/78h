"""Persistence operations for lessons."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.courses.models.lesson import Lesson
from app.modules.courses.models.module import CourseModule


class LessonRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, lesson_id: uuid.UUID) -> Lesson | None:
        """Load a lesson together with its module *and* that module's course.

        The full chain (lesson → module → course → author) is needed for the
        ownership check; without eager loading async SQLAlchemy would fail on
        the implicit lazy load.
        """
        statement = (
            select(Lesson)
            .where(Lesson.id == lesson_id)
            .options(selectinload(Lesson.module).selectinload(CourseModule.course))
        )
        return await self._session.scalar(statement)

    async def list_by_module(self, module_id: uuid.UUID) -> list[Lesson]:
        statement = (
            select(Lesson)
            .where(Lesson.module_id == module_id)
            .order_by(Lesson.position.asc())
        )
        return list(await self._session.scalars(statement))

    async def next_position(self, module_id: uuid.UUID) -> int:
        current = await self._session.scalar(
            select(func.max(Lesson.position)).where(Lesson.module_id == module_id)
        )
        return int(current or 0) + 1

    async def add(
        self,
        *,
        module_id: uuid.UUID,
        title: str,
        description: str | None,
        content: str,
        position: int,
        estimated_duration_minutes: int,
    ) -> Lesson:
        lesson = Lesson(
            module_id=module_id,
            title=title,
            description=description,
            content=content,
            position=position,
            estimated_duration_minutes=estimated_duration_minutes,
        )
        self._session.add(lesson)
        await self._session.flush()
        return lesson

    async def delete(self, lesson: Lesson) -> None:
        await self._session.delete(lesson)
        await self._session.flush()

    async def count_for_module(self, module_id: uuid.UUID) -> int:
        count = await self._session.scalar(
            select(func.count(Lesson.id)).where(Lesson.module_id == module_id)
        )
        return int(count or 0)
