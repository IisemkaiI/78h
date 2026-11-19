"""Persistence operations for course modules."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.courses.models.course import Course
from app.modules.courses.models.module import CourseModule


class ModuleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, module_id: uuid.UUID, *, with_lessons: bool = True) -> CourseModule | None:
        statement = (
            select(CourseModule)
            .where(CourseModule.id == module_id)
            .options(selectinload(CourseModule.course))
        )
        if with_lessons:
            statement = statement.options(selectinload(CourseModule.lessons))
        return await self._session.scalar(statement)

    async def list_by_course(
        self, course_id: uuid.UUID, *, with_lessons: bool = True
    ) -> list[CourseModule]:
        statement = (
            select(CourseModule)
            .where(CourseModule.course_id == course_id)
            .order_by(CourseModule.position.asc())
        )
        if with_lessons:
            statement = statement.options(selectinload(CourseModule.lessons))
        return list(await self._session.scalars(statement))

    async def next_position(self, course_id: uuid.UUID) -> int:
        current = await self._session.scalar(
            select(func.max(CourseModule.position)).where(CourseModule.course_id == course_id)
        )
        return int(current or 0) + 1

    async def add(
        self,
        *,
        course_id: uuid.UUID,
        title: str,
        description: str | None,
        position: int,
    ) -> CourseModule:
        module = CourseModule(
            course_id=course_id,
            title=title,
            description=description,
            position=position,
        )
        self._session.add(module)
        await self._session.flush()
        return module

    async def delete(self, module: CourseModule) -> None:
        await self._session.delete(module)
        await self._session.flush()

    async def count_for_course(self, course_id: uuid.UUID) -> int:
        count = await self._session.scalar(
            select(func.count(CourseModule.id)).where(CourseModule.course_id == course_id)
        )
        return int(count or 0)

    async def load_course(self, course_id: uuid.UUID) -> Course | None:
        """Used to verify that a course exists before creating a module."""
        return await self._session.get(Course, course_id)
