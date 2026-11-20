"""Assessment, quiz history and course instructor ORM models."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric,
    String, Text, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.modules.assessments.constants import (
    ASSIGNMENT_STATUSES, ATTEMPT_STATUSES, QUESTION_TYPES, QUIZ_STATUSES,
    REVIEW_DECISIONS, SUBMISSION_STATUSES,
)


def _values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


class CourseInstructor(Base):
    __tablename__ = "course_instructors"
    __table_args__ = (
        UniqueConstraint("course_id", "instructor_id"),
        Index("ix_course_instructors_instructor_id", "instructor_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("courses.id", ondelete="CASCADE"), nullable=False
    )
    instructor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    assigned_by_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Quiz(Base):
    __tablename__ = "quizzes"
    __table_args__ = (
        CheckConstraint(f"status IN ({_values(QUIZ_STATUSES)})", name="status_values"),
        CheckConstraint("passing_score_percent BETWEEN 0 AND 100", name="passing_score_range"),
        CheckConstraint("time_limit_minutes IS NULL OR time_limit_minutes > 0", name="time_limit_positive"),
        CheckConstraint("max_attempts IS NULL OR max_attempts > 0", name="max_attempts_positive"),
        Index("ix_quizzes_course_status", "course_id", "status"),
        Index("ix_quizzes_lesson_id", "lesson_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    lesson_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lessons.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(20), server_default=text("'draft'"), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    passing_score_percent: Mapped[int] = mapped_column(Integer, server_default=text("70"), nullable=False)
    time_limit_minutes: Mapped[int | None] = mapped_column(Integer)
    max_attempts: Mapped[int | None] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"
    __table_args__ = (
        CheckConstraint(f"question_type IN ({_values(QUESTION_TYPES)})", name="question_type_values"),
        CheckConstraint("points > 0", name="points_positive"),
        UniqueConstraint("quiz_id", "position"),
        Index("ix_quiz_questions_quiz_id", "quiz_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    quiz_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quizzes.id", ondelete="CASCADE"), nullable=False)
    question_type: Mapped[str] = mapped_column(String(30), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"), nullable=False)
    answer_key: Mapped[Any] = mapped_column(JSONB, nullable=False)
    points: Mapped[float] = mapped_column(Numeric(8, 2), server_default=text("1"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"
    __table_args__ = (
        CheckConstraint(f"status IN ({_values(ATTEMPT_STATUSES)})", name="status_values"),
        CheckConstraint("score >= 0 AND max_score >= 0 AND score <= max_score", name="score_range"),
        Index("ix_quiz_attempts_user_quiz_started", "user_id", "quiz_id", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    quiz_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quizzes.id", ondelete="RESTRICT"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    enrollment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enrollments.id", ondelete="RESTRICT"), nullable=False)
    quiz_version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default=text("'in_progress'"), nullable=False)
    score: Mapped[float] = mapped_column(Numeric(8, 2), server_default=text("0"), nullable=False)
    max_score: Mapped[float] = mapped_column(Numeric(8, 2), server_default=text("0"), nullable=False)
    percent: Mapped[float | None] = mapped_column(Numeric(5, 2))
    passed: Mapped[bool | None] = mapped_column(Boolean)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class QuizAnswer(Base):
    __tablename__ = "quiz_answers"
    __table_args__ = (UniqueConstraint("attempt_id", "question_key"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quiz_attempts.id", ondelete="CASCADE"), nullable=False)
    question_key: Mapped[uuid.UUID] = mapped_column(nullable=False)
    answer: Mapped[Any] = mapped_column(JSONB, nullable=False)
    awarded_points: Mapped[float] = mapped_column(Numeric(8, 2), server_default=text("0"), nullable=False)
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class PracticalAssignment(Base):
    __tablename__ = "practical_assignments"
    __table_args__ = (
        CheckConstraint(f"status IN ({_values(ASSIGNMENT_STATUSES)})", name="status_values"),
        CheckConstraint("max_points > 0", name="max_points_positive"),
        Index("ix_practical_assignments_course_status", "course_id", "status"),
        Index("ix_practical_assignments_lesson_id", "lesson_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    lesson_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("lessons.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    requirements: Mapped[str | None] = mapped_column(Text)
    max_points: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    allow_resubmission: Mapped[bool] = mapped_column(Boolean, server_default=text("true"), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default=text("'draft'"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class AssignmentSubmission(Base):
    __tablename__ = "assignment_submissions"
    __table_args__ = (
        UniqueConstraint("assignment_id", "user_id"),
        CheckConstraint(f"status IN ({_values(SUBMISSION_STATUSES)})", name="status_values"),
        Index("ix_assignment_submissions_assignment_status", "assignment_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    assignment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("practical_assignments.id", ondelete="RESTRICT"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    enrollment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("enrollments.id", ondelete="RESTRICT"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), server_default=text("'draft'"), nullable=False)
    draft_text: Mapped[str | None] = mapped_column(Text)
    latest_version: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    current_score: Mapped[float | None] = mapped_column(Numeric(8, 2))
    is_accepted: Mapped[bool | None] = mapped_column(Boolean)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SubmissionVersion(Base):
    __tablename__ = "submission_versions"
    __table_args__ = (UniqueConstraint("submission_id", "version_number"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assignment_submissions.id", ondelete="CASCADE"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AssignmentReview(Base):
    __tablename__ = "assignment_reviews"
    __table_args__ = (
        CheckConstraint(f"decision IN ({_values(REVIEW_DECISIONS)})", name="decision_values"),
        CheckConstraint("score >= 0", name="score_non_negative"),
        Index("ix_assignment_reviews_submission_created", "submission_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    submission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("assignment_submissions.id", ondelete="CASCADE"), nullable=False)
    version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("submission_versions.id", ondelete="RESTRICT"), nullable=False)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    decision: Mapped[str] = mapped_column(String(30), nullable=False)
    score: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
