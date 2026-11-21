"""Lesson-state transitions, course progress and marker reconciliation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from app.modules.assessments.models import (
    AssignmentSubmission, PracticalAssignment, Quiz, QuizAttempt,
)

from app.core.errors import ApiError
from app.core.events import CourseCompleted, publish_event
from app.modules.courses.models.lesson import Lesson
from app.modules.courses.models.module import CourseModule
from app.modules.courses.repositories.lesson import LessonRepository
from app.modules.learning.constants import LearningEventType, LessonState
from app.modules.learning.models.enrollment import Enrollment
from app.modules.learning.models.progress import LessonProgress
from app.modules.learning.repositories.enrollment import (
    EnrollmentRepository,
    LearningEventRepository,
)
from app.modules.learning.repositories.progress import ProgressRepository
from app.modules.learning.schemas import (
    CourseProgressRead,
    LearningEventRead,
    LearningHistoryRead,
    LessonProgressRead,
    LessonProgressUpdateResult,
    RemovedLessonRead,
)
from app.modules.learning.services.access import (
    ensure_active_enrollment,
    ensure_course_available_for_existing_enrollment,
    ensure_enrollment_access,
)
from app.modules.learning.services.progress_calc import calculate_progress
from app.modules.users.models import User


class ProgressService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._enrollments = EnrollmentRepository(session)
        self._progress = ProgressRepository(session)
        self._events = LearningEventRepository(session)
        self._lessons = LessonRepository(session)

    # --- reading ---------------------------------------------------------

    async def get_for_user(
        self, enrollment_id: uuid.UUID, user: User
    ) -> CourseProgressRead:
        enrollment = await self._enrollments.get_by_id(enrollment_id, for_update=True)
        enrollment = ensure_enrollment_access(enrollment, user)
        progress, changed = await self.reconcile(enrollment)
        if changed:
            await self._session.commit()
        return progress

    async def history(
        self, enrollment_id: uuid.UUID, user: User
    ) -> LearningHistoryRead:
        enrollment = await self._enrollments.get_by_id(enrollment_id)
        ensure_enrollment_access(enrollment, user)
        assert enrollment is not None

        events = await self._events.list_for_enrollment(enrollment.id)
        removed = await self._progress.removed_lessons(enrollment.id)
        return LearningHistoryRead(
            events=[
                LearningEventRead(
                    id=event.id,
                    event_type=event.event_type,
                    lesson_id=event.lesson_id,
                    lesson_id_original=event.lesson_id_original,
                    payload=event.payload,
                    created_at=event.created_at,
                )
                for event in events
            ],
            removed_lessons=[
                RemovedLessonRead(
                    lesson_id_original=item.lesson_id_original,
                    module_id_original=item.module_id_original,
                    lesson_title=item.lesson_title_snapshot,
                    module_title=item.module_title_snapshot,
                    state=LessonState(item.state),
                    started_at=item.started_at,
                    completed_at=item.completed_at,
                )
                for item in removed
            ],
        )

    # --- reconciliation --------------------------------------------------

    async def reconcile(self, enrollment: Enrollment) -> tuple[CourseProgressRead, bool]:
        """Recompute the snapshot and synchronise ``completed_at`` + journal.

        The caller must hold the enrollment row lock for mutations and for
        reads that self-heal a stale marker.
        """
        total = await self._progress.total_lessons(enrollment.course_id)
        counts = await self._progress.state_counts(enrollment.id, enrollment.course_id)
        required_quizzes = int(await self._session.scalar(select(func.count(Quiz.id)).where(
            Quiz.course_id == enrollment.course_id, Quiz.status == "published", Quiz.is_required.is_(True),
        )) or 0)
        passed_quizzes = int(await self._session.scalar(select(func.count(func.distinct(QuizAttempt.quiz_id)))
            .join(Quiz, Quiz.id == QuizAttempt.quiz_id)
            .where(Quiz.course_id == enrollment.course_id, Quiz.status == "published",
                   Quiz.is_required.is_(True), QuizAttempt.user_id == enrollment.user_id,
                   QuizAttempt.passed.is_(True))) or 0)
        required_assignments = int(await self._session.scalar(select(func.count(PracticalAssignment.id)).where(
            PracticalAssignment.course_id == enrollment.course_id,
            PracticalAssignment.status == "published", PracticalAssignment.is_required.is_(True),
        )) or 0)
        accepted_assignments = int(await self._session.scalar(select(func.count(func.distinct(AssignmentSubmission.assignment_id)))
            .join(PracticalAssignment, PracticalAssignment.id == AssignmentSubmission.assignment_id)
            .where(PracticalAssignment.course_id == enrollment.course_id,
                   PracticalAssignment.status == "published", PracticalAssignment.is_required.is_(True),
                   AssignmentSubmission.user_id == enrollment.user_id,
                   AssignmentSubmission.status == "graded", AssignmentSubmission.is_accepted.is_(True))) or 0)
        total_required_assessments = required_quizzes + required_assignments
        completed_required_assessments = passed_quizzes + accepted_assignments
        removed_progress = await self._progress.removed_lesson_ids_from_progress(
            enrollment.id
        )
        removed_events = await self._progress.removed_lesson_ids_from_events(
            enrollment.id
        )
        removed_count = len(removed_progress | removed_events)

        snapshot = calculate_progress(
            total_lessons=total,
            completed_lessons=counts.get(LessonState.COMPLETED.value, 0),
            in_progress_lessons=counts.get(LessonState.IN_PROGRESS.value, 0),
            total_required_assessments=total_required_assessments,
            completed_required_assessments=completed_required_assessments,
            removed_lessons_count=removed_count,
        )

        changed = False
        now = datetime.now(UTC)
        if snapshot.is_completed and enrollment.completed_at is None:
            enrollment.completed_at = now
            await self._events.add(
                enrollment_id=enrollment.id,
                event_type=LearningEventType.COURSE_COMPLETED.value,
                payload={
                    "total_lessons": snapshot.total_lessons,
                    "completed_lessons": snapshot.completed_lessons,
                    "progress_percent": snapshot.progress_percent,
                },
            )
            await publish_event(self._session, CourseCompleted(
                user_id=enrollment.user_id,
                enrollment_id=enrollment.id,
                course_slug=enrollment.course.slug,
                course_title=enrollment.course.title,
                completed_at=now.isoformat(),
            ))
            changed = True
        elif not snapshot.is_completed and enrollment.completed_at is not None:
            enrollment.completed_at = None
            await self._events.add(
                enrollment_id=enrollment.id,
                event_type=LearningEventType.COURSE_REOPENED.value,
                payload={
                    "total_lessons": snapshot.total_lessons,
                    "completed_lessons": snapshot.completed_lessons,
                    "progress_percent": snapshot.progress_percent,
                },
            )
            changed = True

        return (
            CourseProgressRead(
                total_lessons=snapshot.total_lessons,
                completed_lessons=snapshot.completed_lessons,
                in_progress_lessons=snapshot.in_progress_lessons,
                not_started_lessons=snapshot.not_started_lessons,
                progress_percent=snapshot.progress_percent,
                is_completed=snapshot.is_completed,
                total_required_assessments=snapshot.total_required_assessments,
                completed_required_assessments=snapshot.completed_required_assessments,
                completed_at=enrollment.completed_at,
                removed_lessons_count=snapshot.removed_lessons_count,
            ),
            changed,
        )

    async def reconcile_course(self, course_id: uuid.UUID) -> None:
        """Synchronise every enrollment of a course after a structural change.

        Called by the authoring service *inside* the structure-changing
        transaction. All enrollment rows are locked in a stable order, so a
        concurrent progress update cannot commit a stale completion marker.
        """
        enrollments = await self._enrollments.list_for_course_for_update(course_id)
        for enrollment in enrollments:
            await self.reconcile(enrollment)

    # --- mutations -------------------------------------------------------

    async def set_lesson_state(
        self,
        enrollment_id: uuid.UUID,
        lesson_id: uuid.UUID,
        user: User,
        state: LessonState,
    ) -> LessonProgressUpdateResult:
        enrollment = await self._enrollments.get_by_id(enrollment_id, for_update=True)
        enrollment = ensure_active_enrollment(enrollment, user)
        assert enrollment is not None
        ensure_course_available_for_existing_enrollment(enrollment)

        lesson = await self._lessons.get_by_id(lesson_id)
        if (
            lesson is None
            or lesson.module is None
            or lesson.module.course_id != enrollment.course_id
        ):
            raise ApiError(404, "lesson_not_found", "Lesson not found.")

        module = lesson.module
        row = await self._progress.get_by_lesson(enrollment.id, lesson.id)
        current_state = LessonState(row.state) if row is not None else LessonState.NOT_STARTED
        target = state
        now = datetime.now(UTC)

        if row is None and target == LessonState.NOT_STARTED:
            progress, _ = await self.reconcile(enrollment)
            return LessonProgressUpdateResult(
                lesson=LessonProgressRead(
                    lesson_id=lesson.id,
                    state=target,
                    started_at=None,
                    completed_at=None,
                    last_viewed_at=None,
                ),
                course_progress=progress,
            )

        if row is None:
            row = await self._progress.add(
                enrollment_id=enrollment.id,
                lesson_id=lesson.id,
                module_id=module.id,
                lesson_title=lesson.title,
                module_title=module.title,
            )

        if enrollment.started_at is None and target in {
            LessonState.IN_PROGRESS,
            LessonState.COMPLETED,
        }:
            enrollment.started_at = now
            await self._events.add(
                enrollment_id=enrollment.id,
                event_type=LearningEventType.STARTED.value,
                payload={"lesson_id": str(lesson.id)},
            )

        if target != current_state:
            row.state = target.value
            if target == LessonState.NOT_STARTED:
                row.started_at = None
                row.completed_at = None
                await self._log_lesson_event(
                    enrollment,
                    lesson,
                    module,
                    LearningEventType.LESSON_RESET,
                    current_state,
                    target,
                    now,
                )
            elif target == LessonState.IN_PROGRESS:
                if row.started_at is None:
                    row.started_at = now
                row.completed_at = None
                if current_state == LessonState.COMPLETED:
                    await self._log_lesson_event(
                        enrollment,
                        lesson,
                        module,
                        LearningEventType.LESSON_REOPENED,
                        current_state,
                        target,
                        now,
                    )
                else:
                    await self._log_lesson_event(
                        enrollment,
                        lesson,
                        module,
                        LearningEventType.LESSON_STARTED,
                        current_state,
                        target,
                        now,
                    )
            else:  # completed
                if row.started_at is None:
                    row.started_at = now
                if current_state != LessonState.COMPLETED or row.completed_at is None:
                    row.completed_at = now
                    await self._log_lesson_event(
                        enrollment,
                        lesson,
                        module,
                        LearningEventType.LESSON_COMPLETED,
                        current_state,
                        target,
                        now,
                    )

        row.last_viewed_at = now
        enrollment.last_activity_at = now
        progress, _ = await self.reconcile(enrollment)
        await self._session.commit()

        return LessonProgressUpdateResult(
            lesson=LessonProgressRead(
                lesson_id=lesson.id,
                state=LessonState(row.state),
                started_at=row.started_at,
                completed_at=row.completed_at,
                last_viewed_at=row.last_viewed_at,
            ),
            course_progress=progress,
        )

    async def _log_lesson_event(
        self,
        enrollment: Enrollment,
        lesson: Lesson,
        module: CourseModule,
        event_type: LearningEventType,
        previous: LessonState,
        target: LessonState,
        now: datetime,
    ) -> None:
        await self._events.add(
            enrollment_id=enrollment.id,
            event_type=event_type.value,
            lesson_id=lesson.id,
            lesson_id_original=lesson.id,
            payload={
                "lesson_title": lesson.title,
                "module_title": module.title,
                "from_state": previous.value,
                "to_state": target.value,
                "at": now.isoformat(),
            },
        )

    @staticmethod
    def lesson_read(
        lesson: Lesson, row: LessonProgress | None
    ) -> LessonProgressRead:
        return LessonProgressRead(
            lesson_id=lesson.id,
            state=LessonState(row.state) if row is not None else LessonState.NOT_STARTED,
            started_at=row.started_at if row is not None else None,
            completed_at=row.completed_at if row is not None else None,
            last_viewed_at=row.last_viewed_at if row is not None else None,
        )
