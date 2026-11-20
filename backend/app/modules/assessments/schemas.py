"""Assessment request and response contracts."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

QuestionType = Literal["single_choice", "multiple_choice", "true_false", "short_text"]
MaterialStatus = Literal["draft", "published", "archived"]
SubmissionStatus = Literal["draft", "submitted", "under_review", "revision_required", "graded"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QuestionInput(StrictModel):
    id: uuid.UUID | None = None
    question_type: QuestionType
    prompt: str = Field(min_length=1, max_length=5000)
    options: list[dict[str, Any]] = Field(default_factory=list)
    answer_key: Any
    points: Decimal = Field(default=Decimal("1"), gt=0, max_digits=8, decimal_places=2)
    position: int = Field(ge=1)
    explanation: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def validate_question_shape(self) -> "QuestionInput":
        if self.question_type in {"single_choice", "multiple_choice"} and len(self.options) < 2:
            raise ValueError("Choice questions require at least two options")
        if self.question_type == "true_false" and self.options:
            raise ValueError("True/false questions do not accept options")
        if self.question_type == "short_text" and (
            not isinstance(self.answer_key, list)
            or not self.answer_key
            or not all(isinstance(value, str) and value.strip() for value in self.answer_key)
        ):
            raise ValueError("Short text answer_key must be a non-empty list of accepted strings")
        return self


class QuizCreate(StrictModel):
    course_id: uuid.UUID
    lesson_id: uuid.UUID | None
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    is_required: bool = False
    passing_score_percent: int = Field(default=70, ge=0, le=100)
    time_limit_minutes: int | None = Field(default=None, gt=0, le=1440)
    max_attempts: int | None = Field(default=None, gt=0, le=100)
    questions: list[QuestionInput] = Field(min_length=1)


class QuizUpdate(StrictModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    is_required: bool | None = None
    passing_score_percent: int | None = Field(default=None, ge=0, le=100)
    time_limit_minutes: int | None = Field(default=None, gt=0, le=1440)
    max_attempts: int | None = Field(default=None, gt=0, le=100)
    questions: list[QuestionInput] | None = Field(default=None, min_length=1)


class QuestionAuthorRead(BaseModel):
    id: uuid.UUID
    question_type: QuestionType
    prompt: str
    options: list[dict[str, Any]]
    answer_key: Any
    points: Decimal
    position: int
    explanation: str | None


class QuestionPublicRead(BaseModel):
    id: uuid.UUID
    question_type: QuestionType
    prompt: str
    options: list[dict[str, Any]]
    points: Decimal
    position: int


class QuizRead(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    lesson_id: uuid.UUID | None
    title: str
    description: str | None
    status: MaterialStatus
    is_required: bool
    passing_score_percent: int
    time_limit_minutes: int | None
    max_attempts: int | None
    version: int
    questions: list[QuestionAuthorRead] = Field(default_factory=list)


class QuizPublicRead(BaseModel):
    id: uuid.UUID
    lesson_id: uuid.UUID
    title: str
    description: str | None
    is_required: bool
    passing_score_percent: int
    time_limit_minutes: int | None
    max_attempts: int | None
    questions: list[QuestionPublicRead]


class AssignmentCreate(StrictModel):
    course_id: uuid.UUID
    lesson_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    requirements: str | None = None
    max_points: Decimal = Field(gt=0, max_digits=8, decimal_places=2)
    due_at: datetime | None = None
    allow_resubmission: bool = True
    is_required: bool = False


class AssignmentUpdate(StrictModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1)
    requirements: str | None = None
    max_points: Decimal | None = Field(default=None, gt=0, max_digits=8, decimal_places=2)
    due_at: datetime | None = None
    allow_resubmission: bool | None = None
    is_required: bool | None = None


class AssignmentRead(BaseModel):
    id: uuid.UUID
    course_id: uuid.UUID
    lesson_id: uuid.UUID
    title: str
    description: str
    requirements: str | None
    max_points: Decimal
    due_at: datetime | None
    allow_resubmission: bool
    is_required: bool
    status: MaterialStatus


class AssignmentLearnerRead(AssignmentRead):
    submission_id: uuid.UUID | None = None
    submission_status: SubmissionStatus | None = None
    current_score: Decimal | None = None
    is_accepted: bool | None = None


class AnswerInput(StrictModel):
    question_id: uuid.UUID
    answer: Any


class AttemptStartRead(BaseModel):
    id: uuid.UUID
    quiz_id: uuid.UUID
    quiz_version: int
    questions: list[QuestionPublicRead]
    expires_at: datetime | None
    started_at: datetime


class AttemptResultRead(BaseModel):
    id: uuid.UUID
    quiz_id: uuid.UUID
    quiz_version: int
    status: str
    score: Decimal
    max_score: Decimal
    percent: Decimal | None
    passed: bool | None
    attempt_number: int
    completed_at: datetime | None
    answers: list[dict[str, Any]] = Field(default_factory=list)


class SubmissionText(StrictModel):
    response_text: str = Field(min_length=1, max_length=100000)


class ReviewInput(StrictModel):
    decision: Literal["accepted", "revision_required"]
    score: Decimal = Field(ge=0, max_digits=8, decimal_places=2)
    comment: str | None = Field(default=None, max_length=10000)


class InstructorCreate(StrictModel):
    instructor_id: uuid.UUID


class SubmissionRead(BaseModel):
    id: uuid.UUID
    assignment_id: uuid.UUID
    user_id: uuid.UUID
    status: SubmissionStatus
    draft_text: str | None
    latest_version: int
    current_score: Decimal | None
    is_accepted: bool | None
    submitted_at: datetime | None
    versions: list[dict[str, Any]] = Field(default_factory=list)
    reviews: list[dict[str, Any]] = Field(default_factory=list)
