"""RBAC vocabulary: role and permission codes used across the platform.

The *initial matrix* (which role receives which permission) lives in the Alembic
seed migration, so historical migrations stay reproducible. This module only
holds the stable identifiers that application code refers to.
"""

from __future__ import annotations

from typing import Final


class RoleCode:
    """Assignable role codes. ``GUEST`` is never attached to an account."""

    GUEST: Final[str] = "guest"
    USER: Final[str] = "user"
    COURSE_AUTHOR: Final[str] = "course_author"
    TEACHER: Final[str] = "teacher"
    ORGANIZATION_EMPLOYEE: Final[str] = "organization_employee"
    ORGANIZATION_MANAGER: Final[str] = "organization_manager"
    ADMIN: Final[str] = "admin"

    ALL: Final[tuple[str, ...]] = (
        GUEST,
        USER,
        COURSE_AUTHOR,
        TEACHER,
        ORGANIZATION_EMPLOYEE,
        ORGANIZATION_MANAGER,
        ADMIN,
    )


class PermissionCode:
    """Permission codes, grouped by future module."""

    # Profile / account
    PROFILE_READ: Final[str] = "profile:read"
    PROFILE_UPDATE: Final[str] = "profile:update"

    # Catalog & authoring (Sprint 2)
    COURSES_READ: Final[str] = "courses:read"
    COURSES_CREATE: Final[str] = "courses:create"
    COURSES_UPDATE: Final[str] = "courses:update"
    COURSES_DELETE: Final[str] = "courses:delete"
    COURSES_PUBLISH: Final[str] = "courses:publish"
    # Administrators manage every course, including drafts of other authors.
    COURSES_MANAGE_ALL: Final[str] = "courses:manage_all"

    # Learning & teaching (Sprint 5+)
    LEARNING_ENROLL: Final[str] = "learning:enroll"
    LEARNING_PARTICIPATE: Final[str] = "learning:participate"
    TEACHING_MANAGE: Final[str] = "teaching:manage"

    # Organization cabinet (Sprint 8+)
    ORGANIZATION_VIEW_MEMBERS: Final[str] = "organization:view_members"
    ORGANIZATION_MANAGE_MEMBERS: Final[str] = "organization:manage_members"
    ORGANIZATION_VIEW_REPORTS: Final[str] = "organization:view_reports"

    # Platform administration (Sprint 9+)
    ADMIN_MANAGE_USERS: Final[str] = "admin:manage_users"
    ADMIN_MANAGE_ROLES: Final[str] = "admin:manage_roles"
    ADMIN_MANAGE_PLATFORM: Final[str] = "admin:manage_platform"
