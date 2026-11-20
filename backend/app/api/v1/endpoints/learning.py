"""Learning process endpoints: enrollment, progress and protected content.

Coarse permissions are enforced by dependencies; ownership and course
availability live in the services, so swapping an enrollment UUID in the URL
never exposes another learner's data.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import SessionDep
from app.modules.auth.dependencies import require_permissions
from app.modules.learning.constants import LessonState
from app.modules.learning.schemas import (
    CourseProgressRead,
    EnrollmentCreate,
    EnrollmentPage,
    EnrollmentRead,
    EnrollmentStatusRead,
    LearningCourseRead,
    LearningHistoryRead,
    LearningLessonContentRead,
    LessonProgressUpdateResult,
    LessonStateUpdate,
)
from app.modules.learning.services.enrollment import EnrollmentService
from app.modules.learning.services.learning import LearningService
from app.modules.learning.services.progress import ProgressService
from app.modules.users.models import User
from app.modules.users.rbac import PermissionCode

router = APIRouter(prefix="/learning", tags=["Learning"])

Enroller = Annotated[
    User, Depends(require_permissions(PermissionCode.ENROLLMENTS_CREATE))
]
EnrollmentReader = Annotated[
    User, Depends(require_permissions(PermissionCode.ENROLLMENTS_READ_OWN))
]
EnrollmentAdmin = Annotated[
    User, Depends(require_permissions(PermissionCode.ENROLLMENTS_MANAGE_ALL))
]
EnrollmentCanceller = Annotated[
    User, Depends(require_permissions(PermissionCode.ENROLLMENTS_CANCEL_OWN))
]
ProgressReader = Annotated[
    User, Depends(require_permissions(PermissionCode.PROGRESS_READ_OWN))
]
ProgressUpdater = Annotated[
    User, Depends(require_permissions(PermissionCode.PROGRESS_UPDATE_OWN))
]

_AUTH_ERRORS = {
    401: {"description": "Not authenticated"},
    403: {"description": "Missing permission or active enrollment required"},
    404: {"description": "Enrollment, course or lesson not found"},
}
_LEARNING_ERRORS = {
    **_AUTH_ERRORS,
    409: {"description": "Course unavailable or enrollment already cancelled"},
}
_VALIDATION = {422: {"description": "Validation error"}}


# --- enrollments ---------------------------------------------------------


@router.post(
    "/enrollments",
    response_model=EnrollmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Enroll in a published course",
    description=(
        "Creates an enrollment or reactivates a previously cancelled one. "
        "Returns 201 for a new enrollment and 200 when the same row is "
        "reactivated; progress and history are preserved."
    ),
    responses={**_LEARNING_ERRORS, **_VALIDATION},
)
async def enroll(
    payload: EnrollmentCreate,
    user: Enroller,
    session: SessionDep,
    response: Response,
) -> EnrollmentRead:
    enrollment, created = await EnrollmentService(session).enroll(
        user, payload.course_id
    )
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return enrollment


@router.get(
    "/enrollments/mine",
    response_model=EnrollmentPage,
    summary="List own enrollments with progress",
    responses=_AUTH_ERRORS,
)
async def list_my_enrollments(
    user: EnrollmentReader,
    session: SessionDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=48)] = 12,
) -> EnrollmentPage:
    return await EnrollmentService(session).list_mine(
        user, page=page, page_size=page_size
    )


@router.get(
    "/enrollments/by-course/{course_id}",
    response_model=EnrollmentStatusRead,
    summary="Read own enrollment status for a course",
    description="Returns `enrolled=false` instead of 404 when there is no row.",
    responses=_AUTH_ERRORS,
)
async def enrollment_status(
    course_id: uuid.UUID,
    user: EnrollmentReader,
    session: SessionDep,
) -> EnrollmentStatusRead:
    return await EnrollmentService(session).get_status(user, course_id)


@router.get(
    "/enrollments",
    response_model=EnrollmentPage,
    summary="List every enrollment (administrators)",
    responses=_AUTH_ERRORS,
)
async def list_all_enrollments(
    user: EnrollmentAdmin,
    session: SessionDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=48)] = 12,
) -> EnrollmentPage:
    return await EnrollmentService(session).list_all(page=page, page_size=page_size)


@router.get(
    "/enrollments/{enrollment_id}",
    response_model=EnrollmentRead,
    summary="Read one enrollment",
    responses=_AUTH_ERRORS,
)
async def read_enrollment(
    enrollment_id: uuid.UUID,
    user: EnrollmentReader,
    session: SessionDep,
) -> EnrollmentRead:
    return await EnrollmentService(session).get_detail(enrollment_id, user)


@router.delete(
    "/enrollments/{enrollment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cancel an enrollment",
    description="Keeps lesson progress and the learning journal untouched.",
    responses=_LEARNING_ERRORS,
)
async def cancel_enrollment(
    enrollment_id: uuid.UUID,
    user: EnrollmentCanceller,
    session: SessionDep,
) -> Response:
    await EnrollmentService(session).cancel(enrollment_id, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/enrollments/{enrollment_id}/start",
    response_model=EnrollmentRead,
    summary="Mark the enrollment as started",
    description="Idempotent: the first call records `started_at` and a journal event.",
    responses=_LEARNING_ERRORS,
)
async def start_enrollment(
    enrollment_id: uuid.UUID,
    user: ProgressUpdater,
    session: SessionDep,
) -> EnrollmentRead:
    return await EnrollmentService(session).start(enrollment_id, user)


# --- progress ------------------------------------------------------------


@router.get(
    "/enrollments/{enrollment_id}/progress",
    response_model=CourseProgressRead,
    summary="Read the current course progress",
    description=(
        "Recomputes the snapshot from current lessons and progress rows. If the "
        "stored completion marker is stale, it is repaired before the response."
    ),
    responses=_AUTH_ERRORS,
)
async def read_progress(
    enrollment_id: uuid.UUID,
    user: ProgressReader,
    session: SessionDep,
) -> CourseProgressRead:
    return await ProgressService(session).get_for_user(enrollment_id, user)


@router.get(
    "/enrollments/{enrollment_id}/history",
    response_model=LearningHistoryRead,
    summary="Read the learning journal and removed lessons",
    responses=_AUTH_ERRORS,
)
async def read_history(
    enrollment_id: uuid.UUID,
    user: ProgressReader,
    session: SessionDep,
) -> LearningHistoryRead:
    return await ProgressService(session).history(enrollment_id, user)


@router.put(
    "/enrollments/{enrollment_id}/lessons/{lesson_id}/progress",
    response_model=LessonProgressUpdateResult,
    summary="Set a lesson state",
    description=(
        "Accepts `not_started`, `in_progress` or `completed`. The course "
        "completion marker and journal are reconciled in the same transaction."
    ),
    responses={**_LEARNING_ERRORS, **_VALIDATION},
)
async def set_lesson_progress(
    enrollment_id: uuid.UUID,
    lesson_id: uuid.UUID,
    payload: LessonStateUpdate,
    user: ProgressUpdater,
    session: SessionDep,
) -> LessonProgressUpdateResult:
    return await ProgressService(session).set_lesson_state(
        enrollment_id,
        lesson_id,
        user,
        LessonState(payload.state),
    )


# --- protected content ---------------------------------------------------


@router.get(
    "/courses/{slug}",
    response_model=LearningCourseRead,
    summary="Read the programme of an enrolled course",
    description=(
        "Returns modules, lessons and per-lesson states without lesson content. "
        "Requires an active enrollment; administrators may inspect published "
        "courses without one."
    ),
    responses=_LEARNING_ERRORS,
)
async def read_learning_course(
    slug: str,
    user: EnrollmentReader,
    session: SessionDep,
    response: Response,
) -> LearningCourseRead:
    response.headers["Cache-Control"] = "private, no-store"
    return await LearningService(session).get_course(slug, user)


@router.get(
    "/courses/{slug}/lessons/{lesson_id}",
    response_model=LearningLessonContentRead,
    summary="Read lesson content",
    description="Protected Markdown content for an enrolled learner.",
    responses={**_LEARNING_ERRORS, 404: {"description": "Course or lesson not found"}},
)
async def read_learning_lesson(
    slug: str,
    lesson_id: uuid.UUID,
    user: EnrollmentReader,
    session: SessionDep,
    response: Response,
) -> LearningLessonContentRead:
    response.headers["Cache-Control"] = "private, no-store"
    return await LearningService(session).get_lesson(slug, lesson_id, user)
