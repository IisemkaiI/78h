"""Ownership rules shared by every authoring service.

The endpoint dependencies already prove that the caller holds the coarse
permission (``courses:update`` etc.). This module proves the caller may touch
*this particular* course. Non-owners receive 404, not 403: revealing that a
draft exists would be an information leak.
"""

from __future__ import annotations

from app.core.errors import ApiError
from app.modules.courses.models.course import Course
from app.modules.users.models import User
from app.modules.users.rbac import PermissionCode


def has_global_course_access(user: User) -> bool:
    """Administrators (``courses:manage_all``) manage every course."""
    return user.has_permissions(PermissionCode.COURSES_MANAGE_ALL)


def course_not_found() -> ApiError:
    return ApiError(404, "course_not_found", "Course not found.")


def ensure_course_access(course: Course | None, user: User) -> Course:
    """Allow the author or an administrator; hide everything else behind 404."""
    if course is None:
        raise course_not_found()
    if has_global_course_access(user):
        return course
    if course.author_id != user.id:
        raise course_not_found()
    return course
