"""Authoring endpoints for courses, modules and lessons.

Thin transport layer: the caller's coarse permission is checked by dependencies,
while record-level ownership (author or ``courses:manage_all``) is enforced by
the services. Someone else's draft is indistinguishable from a missing one.
"""

from __future__ import annotations

import math
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import SessionDep
from app.modules.auth.dependencies import require_permissions
from app.modules.courses.schemas.common import ReorderRequest
from app.modules.courses.schemas.course import (
    CourseCreate,
    CourseDetail,
    CoursePage,
    CourseUpdate,
    course_detail_from_orm,
)
from app.modules.courses.schemas.lesson import LessonCreate, LessonRead, LessonUpdate
from app.modules.courses.schemas.module import ModuleCreate, ModuleRead, ModuleUpdate
from app.modules.courses.services.course import CourseService
from app.modules.courses.services.structure import StructureService
from app.modules.users.models import User
from app.modules.users.rbac import PermissionCode

router = APIRouter(prefix="/courses", tags=["Courses"])

Reader = Annotated[User, Depends(require_permissions(PermissionCode.COURSES_READ))]
Creator = Annotated[User, Depends(require_permissions(PermissionCode.COURSES_CREATE))]
Editor = Annotated[User, Depends(require_permissions(PermissionCode.COURSES_UPDATE))]
Publisher = Annotated[User, Depends(require_permissions(PermissionCode.COURSES_PUBLISH))]
Deleter = Annotated[User, Depends(require_permissions(PermissionCode.COURSES_DELETE))]

_AUTH_ERRORS = {
    401: {"description": "Not authenticated"},
    403: {"description": "Missing permission"},
    404: {"description": "Course, module or lesson not found for this author"},
}
_VALIDATION = {422: {"description": "Validation error"}}


def _page(items: list, total: int, page: int, page_size: int) -> CoursePage:
    return CoursePage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total else 0,
    )


# --- courses -------------------------------------------------------------


@router.get(
    "/mine",
    response_model=CoursePage,
    summary="List own courses (including drafts)",
    description=(
        "Returns every course authored by the caller, with status and content "
        "counts. Administrators use the catalog or open a course by id instead."
    ),
    responses=_AUTH_ERRORS,
)
async def list_my_courses(
    user: Reader,
    session: SessionDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=48)] = 12,
) -> CoursePage:
    items, total = await CourseService(session).list_mine(
        user, page=page, page_size=page_size
    )
    return _page(items, total, page, page_size)


@router.post(
    "",
    response_model=CourseDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create a draft course",
    description=(
        "Creates a course owned by the authenticated author with status `draft`. "
        "The slug is generated from the title; `author_id`, `status` and "
        "`published_at` cannot be supplied by the client."
    ),
    responses={**_AUTH_ERRORS, **_VALIDATION, 404: {"description": "Category not found"}},
)
async def create_course(
    payload: CourseCreate,
    user: Creator,
    session: SessionDep,
) -> CourseDetail:
    return await CourseService(session).create(user, payload)


@router.get(
    "/{course_id}",
    response_model=CourseDetail,
    summary="Read a course for editing",
    description="Available to the author and to administrators only.",
    responses=_AUTH_ERRORS,
)
async def read_course_for_editing(
    course_id: uuid.UUID,
    user: Reader,
    session: SessionDep,
) -> CourseDetail:
    course = await CourseService(session).get_for_editor(course_id, user)
    return course_detail_from_orm(course)


@router.patch(
    "/{course_id}",
    response_model=CourseDetail,
    summary="Update a course",
    description=(
        "Partial update of the author's own course. The slug never changes, so "
        "links to a published course stay valid. Archived courses may still be "
        "edited but remain hidden from the catalog."
    ),
    responses={**_AUTH_ERRORS, **_VALIDATION},
)
async def update_course(
    course_id: uuid.UUID,
    payload: CourseUpdate,
    user: Editor,
    session: SessionDep,
) -> CourseDetail:
    return await CourseService(session).update(course_id, user, payload)


@router.post(
    "/{course_id}/publish",
    response_model=CourseDetail,
    summary="Publish a course",
    description=(
        "Validates the mandatory fields, the category and the module/lesson "
        "structure. The first publication sets `published_at`; republishing "
        "keeps the original date."
    ),
    responses={**_AUTH_ERRORS, 422: {"description": "Course is not ready for publication"}},
)
async def publish_course(
    course_id: uuid.UUID,
    user: Publisher,
    session: SessionDep,
) -> CourseDetail:
    return await CourseService(session).publish(course_id, user)


@router.post(
    "/{course_id}/unpublish",
    response_model=CourseDetail,
    summary="Move a course back to draft",
    description="Removes the course from the public catalog without losing data.",
    responses=_AUTH_ERRORS,
)
async def unpublish_course(
    course_id: uuid.UUID,
    user: Publisher,
    session: SessionDep,
) -> CourseDetail:
    return await CourseService(session).unpublish(course_id, user)


@router.post(
    "/{course_id}/archive",
    response_model=CourseDetail,
    summary="Archive a course",
    description="Hides the course from the public catalog. Nothing is deleted.",
    responses=_AUTH_ERRORS,
)
async def archive_course(
    course_id: uuid.UUID,
    user: Publisher,
    session: SessionDep,
) -> CourseDetail:
    return await CourseService(session).archive(course_id, user)


@router.delete(
    "/{course_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a course",
    description=(
        "Permanently deletes the course with its modules and lessons. Normal "
        "retirement should use `/archive` instead."
    ),
    responses=_AUTH_ERRORS,
)
async def delete_course(
    course_id: uuid.UUID,
    user: Deleter,
    session: SessionDep,
) -> Response:
    await CourseService(session).delete(course_id, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- modules -------------------------------------------------------------


@router.post(
    "/{course_id}/modules",
    response_model=ModuleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Append a module",
    responses={**_AUTH_ERRORS, **_VALIDATION},
)
async def create_module(
    course_id: uuid.UUID,
    payload: ModuleCreate,
    user: Editor,
    session: SessionDep,
) -> ModuleRead:
    return await StructureService(session).add_module(course_id, user, payload)


@router.put(
    "/{course_id}/modules/order",
    response_model=list[ModuleRead],
    summary="Reorder modules",
    description="Accepts every module id of the course exactly once, in the new order.",
    responses={**_AUTH_ERRORS, **_VALIDATION},
)
async def reorder_modules(
    course_id: uuid.UUID,
    payload: ReorderRequest,
    user: Editor,
    session: SessionDep,
) -> list[ModuleRead]:
    return await StructureService(session).reorder_modules(course_id, user, payload.ids)


@router.patch(
    "/{course_id}/modules/{module_id}",
    response_model=ModuleRead,
    summary="Update a module",
    responses={**_AUTH_ERRORS, **_VALIDATION},
)
async def update_module(
    course_id: uuid.UUID,
    module_id: uuid.UUID,
    payload: ModuleUpdate,
    user: Editor,
    session: SessionDep,
) -> ModuleRead:
    return await StructureService(session).update_module(
        course_id, module_id, user, payload
    )


@router.delete(
    "/{course_id}/modules/{module_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a module",
    description=(
        "Deletes the module and its lessons in one transaction, then renumbers "
        "the remaining modules."
    ),
    responses=_AUTH_ERRORS,
)
async def delete_module(
    course_id: uuid.UUID,
    module_id: uuid.UUID,
    user: Editor,
    session: SessionDep,
) -> Response:
    await StructureService(session).delete_module(course_id, module_id, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- lessons -------------------------------------------------------------


@router.post(
    "/{course_id}/modules/{module_id}/lessons",
    response_model=LessonRead,
    status_code=status.HTTP_201_CREATED,
    summary="Append a lesson",
    responses={**_AUTH_ERRORS, **_VALIDATION},
)
async def create_lesson(
    course_id: uuid.UUID,
    module_id: uuid.UUID,
    payload: LessonCreate,
    user: Editor,
    session: SessionDep,
) -> LessonRead:
    return await StructureService(session).add_lesson(
        course_id, module_id, user, payload
    )


@router.put(
    "/{course_id}/modules/{module_id}/lessons/order",
    response_model=list[LessonRead],
    summary="Reorder lessons",
    description="Accepts every lesson id of the module exactly once, in the new order.",
    responses={**_AUTH_ERRORS, **_VALIDATION},
)
async def reorder_lessons(
    course_id: uuid.UUID,
    module_id: uuid.UUID,
    payload: ReorderRequest,
    user: Editor,
    session: SessionDep,
) -> list[LessonRead]:
    return await StructureService(session).reorder_lessons(
        course_id, module_id, user, payload.ids
    )


@router.patch(
    "/{course_id}/modules/{module_id}/lessons/{lesson_id}",
    response_model=LessonRead,
    summary="Update a lesson",
    responses={**_AUTH_ERRORS, **_VALIDATION},
)
async def update_lesson(
    course_id: uuid.UUID,
    module_id: uuid.UUID,
    lesson_id: uuid.UUID,
    payload: LessonUpdate,
    user: Editor,
    session: SessionDep,
) -> LessonRead:
    return await StructureService(session).update_lesson(
        course_id, module_id, lesson_id, user, payload
    )


@router.delete(
    "/{course_id}/modules/{module_id}/lessons/{lesson_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a lesson",
    description="Deletes the lesson and renumbers the remaining lessons of the module.",
    responses=_AUTH_ERRORS,
)
async def delete_lesson(
    course_id: uuid.UUID,
    module_id: uuid.UUID,
    lesson_id: uuid.UUID,
    user: Editor,
    session: SessionDep,
) -> Response:
    await StructureService(session).delete_lesson(
        course_id, module_id, lesson_id, user
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
