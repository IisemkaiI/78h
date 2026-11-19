"""Module and lesson authoring.

Every operation resolves the full ownership chain (lesson → module → course →
author). A mismatched UUID in the URL returns 404, so IDs of other people's
drafts cannot be probed.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.courses.models.course import Course
from app.modules.courses.models.lesson import Lesson
from app.modules.courses.models.module import CourseModule
from app.modules.courses.repositories.course import CourseRepository
from app.modules.courses.repositories.lesson import LessonRepository
from app.modules.courses.repositories.module import ModuleRepository
from app.modules.courses.schemas.lesson import LessonCreate, LessonRead, LessonUpdate
from app.modules.courses.schemas.module import ModuleCreate, ModuleRead, ModuleUpdate
from app.modules.courses.services.access import ensure_course_access
from app.modules.users.models import User

logger = logging.getLogger(__name__)


def _module_not_found() -> ApiError:
    return ApiError(404, "module_not_found", "Module not found.")


def _lesson_not_found() -> ApiError:
    return ApiError(404, "lesson_not_found", "Lesson not found.")


class StructureService:
    """CRUD and ordering for modules and lessons."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._courses = CourseRepository(session)
        self._modules = ModuleRepository(session)
        self._lessons = LessonRepository(session)

    # --- helpers ---------------------------------------------------------

    async def _course(self, course_id: uuid.UUID, user: User) -> Course:
        course = await self._courses.get_by_id(course_id, with_structure=False)
        return ensure_course_access(course, user)

    async def _module(
        self, course_id: uuid.UUID, module_id: uuid.UUID, user: User
    ) -> CourseModule:
        module = await self._modules.get_by_id(module_id, with_lessons=False)
        if module is None or module.course_id != course_id:
            raise _module_not_found()
        ensure_course_access(module.course, user)
        return module

    async def _lesson(
        self,
        course_id: uuid.UUID,
        module_id: uuid.UUID,
        lesson_id: uuid.UUID,
        user: User,
    ) -> Lesson:
        lesson = await self._lessons.get_by_id(lesson_id)
        if (
            lesson is None
            or lesson.module_id != module_id
            or lesson.module.course_id != course_id
        ):
            raise _lesson_not_found()
        ensure_course_access(lesson.module.course, user)
        return lesson

    async def _renumber_modules(self, course_id: uuid.UUID) -> None:
        modules = await self._modules.list_by_course(course_id, with_lessons=False)
        for index, module in enumerate(modules, start=1):
            module.position = index

    async def _renumber_lessons(self, module_id: uuid.UUID) -> None:
        lessons = await self._lessons.list_by_module(module_id)
        for index, lesson in enumerate(lessons, start=1):
            lesson.position = index

    @staticmethod
    def _validate_order(requested: Sequence[uuid.UUID], existing: Sequence[uuid.UUID]) -> None:
        if len(requested) != len(existing) or set(requested) != set(existing):
            raise ApiError(
                422,
                "invalid_order",
                "The new order must contain every child id exactly once.",
                details={
                    "expected": [str(item) for item in existing],
                    "received": [str(item) for item in requested],
                },
            )

    # --- modules ---------------------------------------------------------

    async def add_module(
        self, course_id: uuid.UUID, user: User, payload: ModuleCreate
    ) -> ModuleRead:
        await self._course(course_id, user)
        position = await self._modules.next_position(course_id)
        module = await self._modules.add(
            course_id=course_id,
            title=payload.title,
            description=payload.description,
            position=position,
        )
        await self._session.commit()
        logger.info("Added module %s to course %s", module.id, course_id)

        loaded = await self._modules.get_by_id(module.id)
        assert loaded is not None
        return ModuleRead.model_validate(loaded)

    async def update_module(
        self,
        course_id: uuid.UUID,
        module_id: uuid.UUID,
        user: User,
        payload: ModuleUpdate,
    ) -> ModuleRead:
        module = await self._module(course_id, module_id, user)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(module, field, value)
        await self._session.commit()

        loaded = await self._modules.get_by_id(module.id)
        assert loaded is not None
        return ModuleRead.model_validate(loaded)

    async def delete_module(
        self, course_id: uuid.UUID, module_id: uuid.UUID, user: User
    ) -> None:
        module = await self._module(course_id, module_id, user)
        await self._modules.delete(module)
        # Lessons are removed by ON DELETE CASCADE inside the same transaction.
        await self._renumber_modules(course_id)
        await self._session.commit()
        logger.info("Deleted module %s from course %s", module_id, course_id)

    async def reorder_modules(
        self,
        course_id: uuid.UUID,
        user: User,
        ids: Sequence[uuid.UUID],
    ) -> list[ModuleRead]:
        await self._course(course_id, user)
        modules = await self._modules.list_by_course(course_id, with_lessons=False)
        self._validate_order(ids, [module.id for module in modules])

        by_id = {module.id: module for module in modules}
        ordered = [by_id[module_id] for module_id in ids]
        # Two phases: move everything to negative positions first, so the new
        # numbering can never collide with a position that is still in use.
        for module in ordered:
            module.position = -module.position - 1
        await self._session.flush()
        for index, module in enumerate(ordered, start=1):
            module.position = index
        await self._session.commit()

        reloaded = await self._modules.list_by_course(course_id, with_lessons=True)
        return [ModuleRead.model_validate(module) for module in reloaded]

    # --- lessons ---------------------------------------------------------

    async def add_lesson(
        self,
        course_id: uuid.UUID,
        module_id: uuid.UUID,
        user: User,
        payload: LessonCreate,
    ) -> LessonRead:
        await self._module(course_id, module_id, user)
        position = await self._lessons.next_position(module_id)
        lesson = await self._lessons.add(
            module_id=module_id,
            title=payload.title,
            description=payload.description,
            content=payload.content,
            position=position,
            estimated_duration_minutes=payload.estimated_duration_minutes,
        )
        await self._session.commit()
        logger.info("Added lesson %s to module %s", lesson.id, module_id)
        return LessonRead.model_validate(lesson)

    async def update_lesson(
        self,
        course_id: uuid.UUID,
        module_id: uuid.UUID,
        lesson_id: uuid.UUID,
        user: User,
        payload: LessonUpdate,
    ) -> LessonRead:
        lesson = await self._lesson(course_id, module_id, lesson_id, user)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(lesson, field, value)
        await self._session.commit()

        loaded = await self._lessons.get_by_id(lesson.id)
        assert loaded is not None
        return LessonRead.model_validate(loaded)

    async def delete_lesson(
        self,
        course_id: uuid.UUID,
        module_id: uuid.UUID,
        lesson_id: uuid.UUID,
        user: User,
    ) -> None:
        lesson = await self._lesson(course_id, module_id, lesson_id, user)
        await self._lessons.delete(lesson)
        await self._renumber_lessons(module_id)
        await self._session.commit()
        logger.info("Deleted lesson %s from module %s", lesson_id, module_id)

    async def reorder_lessons(
        self,
        course_id: uuid.UUID,
        module_id: uuid.UUID,
        user: User,
        ids: Sequence[uuid.UUID],
    ) -> list[LessonRead]:
        await self._module(course_id, module_id, user)
        lessons = await self._lessons.list_by_module(module_id)
        self._validate_order(ids, [lesson.id for lesson in lessons])

        by_id = {lesson.id: lesson for lesson in lessons}
        ordered = [by_id[lesson_id] for lesson_id in ids]
        for lesson in ordered:
            lesson.position = -lesson.position - 1
        await self._session.flush()
        for index, lesson in enumerate(ordered, start=1):
            lesson.position = index
        await self._session.commit()

        reloaded = await self._lessons.list_by_module(module_id)
        return [LessonRead.model_validate(lesson) for lesson in reloaded]
