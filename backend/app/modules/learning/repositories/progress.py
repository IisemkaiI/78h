"""Persistence for lesson progress and aggregate counters."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.courses.models.lesson import Lesson
from app.modules.courses.models.module import CourseModule
from app.modules.learning.models.enrollment import LearningEvent
from app.modules.learning.models.progress import LessonProgress


class ProgressRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_lesson(
        self, enrollment_id: uuid.UUID, lesson_id_original: uuid.UUID
    ) -> LessonProgress | None:
        statement = select(LessonProgress).where(
            LessonProgress.enrollment_id == enrollment_id,
            LessonProgress.lesson_id_original == lesson_id_original,
        )
        return await self._session.scalar(statement)

    async def list_for_enrollment(self, enrollment_id: uuid.UUID) -> list[LessonProgress]:
        statement = (
            select(LessonProgress)
            .where(LessonProgress.enrollment_id == enrollment_id)
            .order_by(LessonProgress.created_at.asc())
        )
        return list(await self._session.scalars(statement))

    async def total_lessons(self, course_id: uuid.UUID) -> int:
        statement = (
            select(func.count(Lesson.id))
            .join(CourseModule, CourseModule.id == Lesson.module_id)
            .where(CourseModule.course_id == course_id)
        )
        return int(await self._session.scalar(statement) or 0)

    async def state_counts(
        self, enrollment_id: uuid.UUID, course_id: uuid.UUID
    ) -> dict[str, int]:
        """Count only rows whose lesson still exists in this course."""
        statement = (
            select(LessonProgress.state, func.count(LessonProgress.id))
            .join(Lesson, Lesson.id == LessonProgress.lesson_id)
            .join(CourseModule, CourseModule.id == Lesson.module_id)
            .where(
                LessonProgress.enrollment_id == enrollment_id,
                LessonProgress.lesson_id.is_not(None),
                CourseModule.course_id == course_id,
            )
            .group_by(LessonProgress.state)
        )
        rows = await self._session.execute(statement)
        return {str(state): int(count) for state, count in rows}

    async def removed_lesson_ids_from_progress(
        self, enrollment_id: uuid.UUID
    ) -> set[uuid.UUID]:
        statement = (
            select(LessonProgress.lesson_id_original)
            .where(
                LessonProgress.enrollment_id == enrollment_id,
                LessonProgress.lesson_id.is_(None),
            )
            .distinct()
        )
        return set(await self._session.scalars(statement))

    async def removed_lesson_ids_from_events(
        self, enrollment_id: uuid.UUID
    ) -> set[uuid.UUID]:
        statement = (
            select(LearningEvent.lesson_id_original)
            .where(
                LearningEvent.enrollment_id == enrollment_id,
                LearningEvent.lesson_id.is_(None),
                LearningEvent.lesson_id_original.is_not(None),
            )
            .distinct()
        )
        return set(await self._session.scalars(statement))

    async def removed_lessons(self, enrollment_id: uuid.UUID) -> list[LessonProgress]:
        statement = (
            select(LessonProgress)
            .where(
                LessonProgress.enrollment_id == enrollment_id,
                LessonProgress.lesson_id.is_(None),
            )
            .order_by(LessonProgress.created_at.asc())
        )
        return list(await self._session.scalars(statement))

    async def add(
        self,
        *,
        enrollment_id: uuid.UUID,
        lesson_id: uuid.UUID,
        module_id: uuid.UUID,
        lesson_title: str,
        module_title: str,
    ) -> LessonProgress:
        progress = LessonProgress(
            enrollment_id=enrollment_id,
            lesson_id=lesson_id,
            lesson_id_original=lesson_id,
            module_id_original=module_id,
            lesson_title_snapshot=lesson_title,
            module_title_snapshot=module_title,
        )
        self._session.add(progress)
        await self._session.flush()
        return progress
