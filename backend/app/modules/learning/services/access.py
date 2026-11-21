"""Record-level access rules for learning.

Permission dependencies prove the coarse capability. These helpers prove that
the caller owns the enrollment or holds ``*:manage_all``. A foreign enrollment
is reported as 404, exactly like a missing one.
"""

from __future__ import annotations

from app.core.errors import ApiError
from app.modules.courses.constants import CourseStatus
from app.modules.courses.models.course import Course
from app.modules.learning.models.enrollment import Enrollment
from app.modules.users.models import User
from app.modules.users.rbac import PermissionCode


def has_any_learning_admin_right(user: User) -> bool:
    return user.has_permissions(PermissionCode.ENROLLMENTS_MANAGE_ALL) or user.has_permissions(
        PermissionCode.PROGRESS_MANAGE_ALL
    )


def has_global_learning_access(user: User) -> bool:
    return has_any_learning_admin_right(user)


def is_course_available(course: Course) -> bool:
    return (
        course.status == CourseStatus.PUBLISHED.value
        and course.category is not None
        and course.category.is_active
    )


def ensure_enrollment_access(enrollment: Enrollment | None, user: User) -> Enrollment:
    if enrollment is None:
        raise ApiError(404, "enrollment_not_found", "Enrollment not found.")
    if has_any_learning_admin_right(user):
        return enrollment
    if enrollment.user_id != user.id:
        raise ApiError(404, "enrollment_not_found", "Enrollment not found.")
    return enrollment


def ensure_active_enrollment(enrollment: Enrollment | None, user: User) -> Enrollment:
    enrollment = ensure_enrollment_access(enrollment, user)
    if not enrollment.is_active:
        raise ApiError(
            403,
            "enrollment_required",
            "An active enrollment is required.",
        )
    return enrollment


def ensure_course_available_for_learning(course: Course) -> Course:
    if not is_course_available(course):
        raise ApiError(
            409,
            "course_not_available",
            "The course is no longer available for learning.",
        )
    return course


def ensure_course_available_for_existing_enrollment(enrollment: Enrollment) -> Course:
    """Allow an active learner to finish a course archived after enrollment."""
    course = enrollment.course
    if is_course_available(course) or (
        enrollment.is_active and course.status == CourseStatus.ARCHIVED.value
    ):
        return course
    raise ApiError(409, "course_not_available", "The course is no longer available for learning.")
