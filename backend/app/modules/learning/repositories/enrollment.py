"""Persistence for enrollments and the learning journal."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.courses.models.course import Course
from app.modules.learning.models.enrollment import Enrollment, LearningEvent


def _with_course():
    return (
        selectinload(Enrollment.course).selectinload(Course.category),
        selectinload(Enrollment.course).selectinload(Course.author),
    )


class EnrollmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(
        self, enrollment_id: uuid.UUID, *, for_update: bool = False
    ) -> Enrollment | None:
        statement = (
            select(Enrollment)
            .where(Enrollment.id == enrollment_id)
            .options(*_with_course())
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def get_by_user_and_course(
        self,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        *,
        for_update: bool = False,
    ) -> Enrollment | None:
        statement = (
            select(Enrollment)
            .where(
                Enrollment.user_id == user_id,
                Enrollment.course_id == course_id,
            )
            .options(*_with_course())
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._session.scalar(statement)

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        *,
        offset: int,
        limit: int,
        for_update: bool = False,
    ) -> tuple[list[Enrollment], int]:
        statement = (
            select(Enrollment)
            .where(Enrollment.user_id == user_id)
            .order_by(
                Enrollment.last_activity_at.desc().nulls_last(),
                Enrollment.enrolled_at.desc(),
            )
            .offset(offset)
            .limit(limit)
            .options(*_with_course())
        )
        if for_update:
            statement = statement.with_for_update()
        total = await self._session.scalar(
            select(func.count(Enrollment.id)).where(Enrollment.user_id == user_id)
        )
        return list(await self._session.scalars(statement)), int(total or 0)

    async def list_all(
        self, *, offset: int, limit: int
    ) -> tuple[list[Enrollment], int]:
        statement = (
            select(Enrollment)
            .order_by(Enrollment.created_at.desc())
            .offset(offset)
            .limit(limit)
            .options(*_with_course())
        )
        total = await self._session.scalar(select(func.count(Enrollment.id)))
        return list(await self._session.scalars(statement)), int(total or 0)

    async def list_for_course_for_update(self, course_id: uuid.UUID) -> list[Enrollment]:
        statement = (
            select(Enrollment)
            .where(Enrollment.course_id == course_id)
            .order_by(Enrollment.created_at.asc())
            .with_for_update()
        )
        return list(await self._session.scalars(statement))

    async def exists_for_course(self, course_id: uuid.UUID) -> bool:
        return (
            await self._session.scalar(
                select(Enrollment.id).where(Enrollment.course_id == course_id).limit(1)
            )
            is not None
        )

    async def add(self, *, user_id: uuid.UUID, course_id: uuid.UUID) -> Enrollment:
        enrollment = Enrollment(user_id=user_id, course_id=course_id)
        self._session.add(enrollment)
        await self._session.flush()
        return enrollment


class LearningEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        *,
        enrollment_id: uuid.UUID,
        event_type: str,
        lesson_id: uuid.UUID | None = None,
        lesson_id_original: uuid.UUID | None = None,
        payload: dict | None = None,
    ) -> LearningEvent:
        event = LearningEvent(
            enrollment_id=enrollment_id,
            event_type=event_type,
            lesson_id=lesson_id,
            lesson_id_original=lesson_id_original,
            payload=payload or {},
        )
        self._session.add(event)
        await self._session.flush()
        return event

    async def list_for_enrollment(self, enrollment_id: uuid.UUID) -> list[LearningEvent]:
        statement = (
            select(LearningEvent)
            .where(LearningEvent.enrollment_id == enrollment_id)
            .order_by(LearningEvent.created_at.asc(), LearningEvent.id.asc())
        )
        return list(await self._session.scalars(statement))
