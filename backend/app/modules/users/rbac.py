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

    # Learning & teaching (Sprint 4+)
    ENROLLMENTS_CREATE: Final[str] = "enrollments:create"
    ENROLLMENTS_READ_OWN: Final[str] = "enrollments:read_own"
    ENROLLMENTS_CANCEL_OWN: Final[str] = "enrollments:cancel_own"
    ENROLLMENTS_MANAGE_ALL: Final[str] = "enrollments:manage_all"
    PROGRESS_READ_OWN: Final[str] = "progress:read_own"
    PROGRESS_UPDATE_OWN: Final[str] = "progress:update_own"
    PROGRESS_MANAGE_ALL: Final[str] = "progress:manage_all"

    # Quizzes, practical work and instructor assignments (Sprint 5)
    ASSESSMENTS_MANAGE_OWN: Final[str] = "assessments:manage_own"
    ASSESSMENTS_PUBLISH_OWN: Final[str] = "assessments:publish_own"
    ASSESSMENTS_INSTRUCTORS_MANAGE: Final[str] = "assessments:instructors_manage"
    ASSESSMENTS_ATTEMPT: Final[str] = "assessments:attempt"
    ASSESSMENTS_READ_OWN_RESULTS: Final[str] = "assessments:read_own_results"
    ASSESSMENTS_SUBMIT: Final[str] = "assessments:submit"
    ASSESSMENTS_REVIEW: Final[str] = "assessments:review"
    ASSESSMENTS_MANAGE_ALL: Final[str] = "assessments:manage_all"

    # Certificates (Sprint 6)
    CERTIFICATES_ISSUE_SELF: Final[str] = "certificates:issue_self"
    CERTIFICATES_READ_SELF: Final[str] = "certificates:read_self"

    # Legacy learning permissions (kept for backward compatibility).
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
