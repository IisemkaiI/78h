"""Practical assignment submissions, instructor review and course staffing."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.core.events import AssignmentReviewed, publish_event
from app.modules.assessments.models import (
    AssignmentReview, AssignmentSubmission, CourseInstructor,
    PracticalAssignment, SubmissionVersion,
)
from app.modules.assessments.schemas import (
    AssignmentCreate, AssignmentUpdate, ReviewInput,
)
from app.modules.courses.models import Course, CourseModule, Lesson
from app.modules.learning.models import Enrollment
from app.modules.learning.services.progress import ProgressService
from app.modules.users.models import User
from app.modules.users.rbac import PermissionCode


class AssignmentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _course(self, course_id: uuid.UUID, user: User) -> Course:
        course = await self.session.get(Course, course_id)
        if course is None or (
            course.author_id != user.id
            and not user.has_permissions(PermissionCode.ASSESSMENTS_MANAGE_ALL)
        ):
            raise ApiError(404, "course_not_found", "Course not found.")
        return course

    async def _lesson(self, course_id: uuid.UUID, lesson_id: uuid.UUID) -> None:
        lesson = await self.session.scalar(select(Lesson).join(CourseModule).where(
            Lesson.id == lesson_id, CourseModule.course_id == course_id,
        ))
        if lesson is None:
            raise ApiError(422, "lesson_course_mismatch", "Lesson must belong to the selected course.")

    async def _assignment(self, assignment_id: uuid.UUID) -> PracticalAssignment:
        assignment = await self.session.get(PracticalAssignment, assignment_id)
        if assignment is None:
            raise ApiError(404, "assignment_not_found", "Assignment not found.")
        return assignment

    async def _can_review(self, course_id: uuid.UUID, user: User) -> bool:
        if user.has_permissions(PermissionCode.ASSESSMENTS_MANAGE_ALL):
            return True
        course = await self.session.get(Course, course_id)
        if course is not None and course.author_id == user.id:
            return True
        return bool(await self.session.scalar(select(CourseInstructor.id).where(
            CourseInstructor.course_id == course_id,
            CourseInstructor.instructor_id == user.id,
        )))

    async def create(self, user: User, payload: AssignmentCreate) -> PracticalAssignment:
        await self._course(payload.course_id, user)
        await self._lesson(payload.course_id, payload.lesson_id)
        assignment = PracticalAssignment(**payload.model_dump())
        self.session.add(assignment)
        await self.session.commit()
        return assignment

    async def list_for_course(self, course_id: uuid.UUID, user: User) -> list[PracticalAssignment]:
        if not await self._can_review(course_id, user):
            raise ApiError(404, "course_not_found", "Course not found.")
        return list(await self.session.scalars(select(PracticalAssignment).where(
            PracticalAssignment.course_id == course_id,
        ).order_by(PracticalAssignment.created_at)))

    async def list_teaching_courses(self, user: User) -> list[dict[str, Any]]:
        statement = select(Course).outerjoin(CourseInstructor, CourseInstructor.course_id == Course.id)
        if not user.has_permissions(PermissionCode.ASSESSMENTS_MANAGE_ALL):
            statement = statement.where(or_(
                Course.author_id == user.id, CourseInstructor.instructor_id == user.id,
            ))
        rows = list(await self.session.scalars(statement.distinct().order_by(Course.title)))
        return [{"id": course.id, "title": course.title, "slug": course.slug,
                 "assignments": [
                     {"id": item.id, "title": item.title, "status": item.status,
                      "is_required": item.is_required}
                     for item in await self.list_for_course(course.id, user)
                 ]} for course in rows]

    async def update(self, assignment_id: uuid.UUID, user: User, payload: AssignmentUpdate) -> PracticalAssignment:
        assignment = await self._assignment(assignment_id)
        await self._course(assignment.course_id, user)
        changes = payload.model_dump(exclude_unset=True)
        if "is_required" in changes and assignment.status == "published":
            raise ApiError(409, "published_requirement_locked", "Unpublish the assignment before changing whether it is required.")
        for name, value in changes.items():
            setattr(assignment, name, value)
        await self.session.flush()
        if assignment.status == "published" and assignment.is_required:
            await ProgressService(self.session).reconcile_course(assignment.course_id)
        await self.session.commit()
        return assignment

    async def set_status(self, assignment_id: uuid.UUID, user: User, status: str) -> PracticalAssignment:
        assignment = await self._assignment(assignment_id)
        await self._course(assignment.course_id, user)
        assignment.status = status
        await self.session.flush()
        if status == "archived" or assignment.is_required:
            await ProgressService(self.session).reconcile_course(assignment.course_id)
        await self.session.commit()
        return assignment

    async def _active_enrollment(self, assignment: PracticalAssignment, user: User) -> Enrollment:
        enrollment = await self.session.scalar(select(Enrollment).where(
            Enrollment.user_id == user.id,
            Enrollment.course_id == assignment.course_id,
            Enrollment.status == "active",
        ).with_for_update())
        course = await self.session.get(Course, assignment.course_id)
        if assignment.status != "published" or enrollment is None or course is None or course.status != "published":
            raise ApiError(403, "enrollment_required", "An active enrollment in the published course is required.")
        return enrollment

    async def _submission(self, assignment: PracticalAssignment, user: User, enrollment: Enrollment) -> AssignmentSubmission:
        row = await self.session.scalar(select(AssignmentSubmission).where(
            AssignmentSubmission.assignment_id == assignment.id,
            AssignmentSubmission.user_id == user.id,
        ).with_for_update())
        if row is None:
            row = AssignmentSubmission(
                assignment_id=assignment.id, user_id=user.id, enrollment_id=enrollment.id,
            )
            self.session.add(row)
            await self.session.flush()
        return row

    async def save_draft(self, assignment_id: uuid.UUID, user: User, text: str) -> AssignmentSubmission:
        assignment = await self._assignment(assignment_id)
        enrollment = await self._active_enrollment(assignment, user)
        row = await self._submission(assignment, user, enrollment)
        if row.status not in {"draft", "revision_required"}:
            raise ApiError(409, "submission_locked", "Only a draft or returned work can be edited.")
        if row.status == "revision_required" and not assignment.allow_resubmission:
            raise ApiError(409, "resubmission_not_allowed", "Resubmission is disabled for this assignment.")
        row.draft_text = text
        await self.session.commit()
        return row

    async def submit(self, assignment_id: uuid.UUID, user: User) -> AssignmentSubmission:
        assignment = await self._assignment(assignment_id)
        enrollment = await self._active_enrollment(assignment, user)
        row = await self._submission(assignment, user, enrollment)
        if row.status not in {"draft", "revision_required"}:
            raise ApiError(409, "submission_not_editable", "This work cannot be submitted in its current state.")
        if row.status == "revision_required" and not assignment.allow_resubmission:
            raise ApiError(409, "resubmission_not_allowed", "Resubmission is disabled for this assignment.")
        if not row.draft_text or not row.draft_text.strip():
            raise ApiError(422, "empty_submission", "Save a non-empty text response before submitting.")
        row.latest_version += 1
        version = SubmissionVersion(
            submission_id=row.id, version_number=row.latest_version,
            response_text=row.draft_text,
        )
        self.session.add(version)
        row.draft_text = None
        row.status = "submitted"
        row.submitted_at = datetime.now(UTC)
        row.is_accepted = None
        await self.session.commit()
        return row

    async def own_submission(self, assignment_id: uuid.UUID, user: User) -> dict[str, Any] | None:
        assignment = await self._assignment(assignment_id)
        row = await self.session.scalar(select(AssignmentSubmission).where(
            AssignmentSubmission.assignment_id == assignment.id,
            AssignmentSubmission.user_id == user.id,
        ))
        if row is None:
            return None
        return await self._submission_dict(row)

    async def list_submissions(self, assignment_id: uuid.UUID, user: User) -> list[dict[str, Any]]:
        assignment = await self._assignment(assignment_id)
        if not await self._can_review(assignment.course_id, user):
            raise ApiError(404, "assignment_not_found", "Assignment not found.")
        rows = list(await self.session.scalars(select(AssignmentSubmission).where(
            AssignmentSubmission.assignment_id == assignment.id,
        ).order_by(AssignmentSubmission.submitted_at)))
        return [await self._submission_dict(row) for row in rows]

    async def mark_under_review(self, submission_id: uuid.UUID, reviewer: User) -> dict[str, Any]:
        row = await self._submission_by_id(submission_id)
        assignment = await self._assignment(row.assignment_id)
        if row.user_id == reviewer.id:
            raise ApiError(403, "self_review_forbidden", "You cannot review your own work.")
        if not await self._can_review(assignment.course_id, reviewer):
            raise ApiError(404, "submission_not_found", "Submission not found.")
        if row.status != "submitted":
            raise ApiError(409, "invalid_submission_state", "Only submitted work can enter review.")
        row.status = "under_review"
        await self.session.commit()
        return await self._submission_dict(row)

    async def review(self, submission_id: uuid.UUID, reviewer: User, payload: ReviewInput) -> dict[str, Any]:
        row = await self._submission_by_id(submission_id, lock=True)
        assignment = await self._assignment(row.assignment_id)
        if row.user_id == reviewer.id:
            raise ApiError(403, "self_review_forbidden", "You cannot review your own work.")
        if not await self._can_review(assignment.course_id, reviewer):
            raise ApiError(404, "submission_not_found", "Submission not found.")
        if row.status not in {"under_review", "submitted"}:
            raise ApiError(409, "invalid_submission_state", "This work is not awaiting review.")
        if payload.score > assignment.max_points:
            raise ApiError(422, "score_exceeds_maximum", "The score cannot exceed the assignment maximum.")
        version = await self.session.scalar(select(SubmissionVersion).where(
            SubmissionVersion.submission_id == row.id,
            SubmissionVersion.version_number == row.latest_version,
        ))
        if version is None:
            raise ApiError(409, "submission_version_missing", "No submitted version is available for review.")
        self.session.add(AssignmentReview(
            submission_id=row.id, version_id=version.id, reviewer_id=reviewer.id,
            decision=payload.decision, score=payload.score, comment=payload.comment,
        ))
        row.status = "graded" if payload.decision == "accepted" else "revision_required"
        row.current_score = payload.score
        row.is_accepted = payload.decision == "accepted"
        await self.session.flush()
        course = await self.session.get(Course, assignment.course_id)
        await publish_event(self.session, AssignmentReviewed(
            user_id=row.user_id, submission_id=row.id, version_number=row.latest_version,
            course_slug=course.slug, assignment_title=assignment.title,
            decision=payload.decision, score=payload.score,
        ))
        await ProgressService(self.session).reconcile_course(assignment.course_id)
        await self.session.commit()
        return await self._submission_dict(row)

    async def _submission_by_id(self, submission_id: uuid.UUID, *, lock: bool = False) -> AssignmentSubmission:
        statement = select(AssignmentSubmission).where(AssignmentSubmission.id == submission_id)
        if lock:
            statement = statement.with_for_update()
        row = await self.session.scalar(statement)
        if row is None:
            raise ApiError(404, "submission_not_found", "Submission not found.")
        return row

    async def _submission_dict(self, row: AssignmentSubmission) -> dict[str, Any]:
        versions = list(await self.session.scalars(select(SubmissionVersion).where(
            SubmissionVersion.submission_id == row.id,
        ).order_by(SubmissionVersion.version_number)))
        reviews = list(await self.session.scalars(select(AssignmentReview).where(
            AssignmentReview.submission_id == row.id,
        ).order_by(AssignmentReview.created_at)))
        return {
            "id": row.id, "assignment_id": row.assignment_id, "user_id": row.user_id,
            "status": row.status, "draft_text": row.draft_text,
            "latest_version": row.latest_version, "current_score": row.current_score,
            "is_accepted": row.is_accepted, "submitted_at": row.submitted_at,
            "versions": [{"id": item.id, "version_number": item.version_number,
                          "response_text": item.response_text, "submitted_at": item.submitted_at}
                         for item in versions],
            "reviews": [{"id": item.id, "version_id": item.version_id,
                         "reviewer_id": item.reviewer_id, "decision": item.decision,
                         "score": item.score, "comment": item.comment,
                         "created_at": item.created_at} for item in reviews],
        }

    async def add_instructor(self, course_id: uuid.UUID, user: User, instructor_id: uuid.UUID) -> CourseInstructor:
        course = await self._course(course_id, user)
        instructor = await self.session.get(User, instructor_id)
        if instructor is None or not instructor.has_role("teacher"):
            raise ApiError(422, "teacher_required", "The selected user must have the teacher role.")
        current = await self.session.scalar(select(CourseInstructor).where(
            CourseInstructor.course_id == course.id,
            CourseInstructor.instructor_id == instructor.id,
        ))
        if current:
            return current
        row = CourseInstructor(course_id=course.id, instructor_id=instructor.id, assigned_by_id=user.id)
        self.session.add(row)
        await self.session.commit()
        return row

    async def remove_instructor(self, course_id: uuid.UUID, instructor_id: uuid.UUID, user: User) -> None:
        await self._course(course_id, user)
        row = await self.session.scalar(select(CourseInstructor).where(
            CourseInstructor.course_id == course_id,
            CourseInstructor.instructor_id == instructor_id,
        ))
        if row is None:
            raise ApiError(404, "instructor_assignment_not_found", "Instructor assignment not found.")
        await self.session.delete(row)
        await self.session.commit()

    async def list_instructors(self, course_id: uuid.UUID, user: User) -> list[dict[str, Any]]:
        await self._course(course_id, user)
        rows = list(await self.session.scalars(select(CourseInstructor).where(
            CourseInstructor.course_id == course_id,
        ).order_by(CourseInstructor.created_at)))
        result = []
        for row in rows:
            instructor = await self.session.get(User, row.instructor_id)
            result.append({"course_id": row.course_id, "instructor_id": row.instructor_id,
                           "display_name": instructor.display_name if instructor else "",
                           "assigned_by_id": row.assigned_by_id, "created_at": row.created_at})
        return result
