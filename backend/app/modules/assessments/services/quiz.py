"""Quiz authoring and immutable attempt workflows."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.core.events import QuizCompleted, publish_event
from app.modules.assessments.models import Quiz, QuizAnswer, QuizAttempt, QuizQuestion
from app.modules.assessments.schemas import AnswerInput, QuizCreate, QuizUpdate
from app.modules.courses.models import Course, CourseModule, Lesson
from app.modules.learning.models import Enrollment
from app.modules.learning.services.progress import ProgressService
from app.modules.users.models import User
from app.modules.users.rbac import PermissionCode


def _not_found() -> ApiError:
    return ApiError(404, "quiz_not_found", "Quiz not found.")


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).casefold()


class QuizService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _course(self, course_id: uuid.UUID, user: User, *, lesson_id: uuid.UUID | None = None) -> Course:
        course = await self.session.get(Course, course_id)
        if course is None:
            raise ApiError(404, "course_not_found", "Course not found.")
        if not user.has_permissions(PermissionCode.ASSESSMENTS_MANAGE_ALL) and course.author_id != user.id:
            raise ApiError(404, "course_not_found", "Course not found.")
        if lesson_id is not None:
            lesson = await self.session.scalar(select(Lesson).join(CourseModule).where(
                Lesson.id == lesson_id, CourseModule.course_id == course_id,
            ))
            if lesson is None:
                raise ApiError(422, "lesson_course_mismatch", "Lesson must belong to the selected course.")
        return course

    @staticmethod
    def _question_values(question: QuizQuestion) -> dict[str, Any]:
        return {
            "id": question.id, "question_type": question.question_type,
            "prompt": question.prompt, "options": question.options,
            "answer_key": question.answer_key, "points": question.points,
            "position": question.position, "explanation": question.explanation,
        }

    async def _questions(self, quiz_id: uuid.UUID) -> list[QuizQuestion]:
        return list(await self.session.scalars(
            select(QuizQuestion).where(QuizQuestion.quiz_id == quiz_id).order_by(QuizQuestion.position)
        ))

    async def create(self, user: User, payload: QuizCreate) -> dict[str, Any]:
        await self._course(payload.course_id, user, lesson_id=payload.lesson_id)
        quiz = Quiz(
            course_id=payload.course_id, lesson_id=payload.lesson_id,
            title=payload.title, description=payload.description,
            is_required=payload.is_required, passing_score_percent=payload.passing_score_percent,
            time_limit_minutes=payload.time_limit_minutes, max_attempts=payload.max_attempts,
        )
        self.session.add(quiz)
        await self.session.flush()
        self._replace_questions(quiz, payload.questions)
        await self.session.commit()
        return await self.get_author(quiz.id, user)

    def _replace_questions(self, quiz: Quiz, inputs: list[Any]) -> None:
        seen: set[int] = set()
        for item in inputs:
            if item.position in seen:
                raise ApiError(422, "duplicate_question_position", "Question positions must be unique.")
            seen.add(item.position)
            option_ids = [str(option.get("id", "")) for option in item.options]
            if item.question_type in {"single_choice", "multiple_choice"}:
                if (any(not value for value in option_ids)
                        or any(not str(option.get("text", "")).strip() for option in item.options)
                        or len(option_ids) != len(set(option_ids))):
                    raise ApiError(422, "invalid_options", "Every choice option needs a unique id.")
                correct = item.answer_key if isinstance(item.answer_key, list) else [item.answer_key]
                if not correct or not set(map(str, correct)).issubset(set(option_ids)):
                    raise ApiError(422, "invalid_answer_key", "Correct choices must refer to defined option ids.")
                if item.question_type == "single_choice" and len(correct) != 1:
                    raise ApiError(422, "invalid_answer_key", "Single-choice questions require one correct option.")
            if item.question_type == "true_false" and not isinstance(item.answer_key, bool):
                raise ApiError(422, "invalid_answer_key", "True/false answer_key must be boolean.")
            self.session.add(QuizQuestion(
                quiz_id=quiz.id, question_type=item.question_type, prompt=item.prompt,
                options=item.options, answer_key=item.answer_key, points=item.points,
                position=item.position, explanation=item.explanation,
            ))

    async def get_author(self, quiz_id: uuid.UUID, user: User) -> dict[str, Any]:
        quiz = await self.session.get(Quiz, quiz_id)
        if quiz is None:
            raise _not_found()
        await self._course(quiz.course_id, user)
        return {**self._quiz_dict(quiz), "questions": [self._question_values(q) for q in await self._questions(quiz.id)]}

    @staticmethod
    def _quiz_dict(quiz: Quiz) -> dict[str, Any]:
        return {name: getattr(quiz, name) for name in (
            "id", "course_id", "lesson_id", "title", "description", "status",
            "is_required", "passing_score_percent", "time_limit_minutes", "max_attempts", "version",
        )}

    async def list_for_course(self, course_id: uuid.UUID, user: User) -> list[dict[str, Any]]:
        await self._course(course_id, user)
        quizzes = list(await self.session.scalars(select(Quiz).where(Quiz.course_id == course_id).order_by(Quiz.created_at)))
        return [await self.get_author(q.id, user) for q in quizzes]

    async def update(self, quiz_id: uuid.UUID, user: User, payload: QuizUpdate) -> dict[str, Any]:
        quiz = await self.session.scalar(select(Quiz).where(Quiz.id == quiz_id).with_for_update())
        if quiz is None:
            raise _not_found()
        await self._course(quiz.course_id, user)
        changes = payload.model_dump(exclude_unset=True, exclude={"questions"})
        if "is_required" in changes and quiz.status == "published":
            raise ApiError(409, "published_requirement_locked", "Unpublish the quiz before changing whether it is required.")
        questions = payload.questions if "questions" in payload.model_fields_set else None
        for name, value in changes.items():
            setattr(quiz, name, value)
        if questions is not None:
            await self.session.execute(
                QuizQuestion.__table__.delete().where(QuizQuestion.quiz_id == quiz.id)
            )
            self._replace_questions(quiz, questions)
        quiz.version += 1
        await self.session.commit()
        return await self.get_author(quiz.id, user)

    async def set_status(self, quiz_id: uuid.UUID, user: User, status: str) -> dict[str, Any]:
        quiz = await self.session.get(Quiz, quiz_id)
        if quiz is None:
            raise _not_found()
        await self._course(quiz.course_id, user)
        if status == "published" and not await self.session.scalar(select(func.count()).select_from(QuizQuestion).where(QuizQuestion.quiz_id == quiz.id)):
            raise ApiError(409, "quiz_has_no_questions", "A quiz needs at least one question before publication.")
        quiz.status = status
        await self.session.flush()
        if status == "archived" or quiz.is_required:
            await ProgressService(self.session).reconcile_course(quiz.course_id)
        await self.session.commit()
        return await self.get_author(quiz.id, user)

    async def _active_enrollment(self, course_id: uuid.UUID, user_id: uuid.UUID) -> Enrollment:
        enrollment = await self.session.scalar(select(Enrollment).where(
            Enrollment.course_id == course_id, Enrollment.user_id == user_id,
            Enrollment.status == "active",
        ).with_for_update())
        if enrollment is None:
            raise ApiError(403, "enrollment_required", "An active enrollment is required.")
        course = await self.session.get(Course, course_id)
        if course is None or course.status not in {"published", "archived"}:
            raise ApiError(409, "course_not_available", "The course is not available for learning.")
        return enrollment

    async def start(self, quiz_id: uuid.UUID, user: User) -> dict[str, Any]:
        quiz = await self.session.scalar(select(Quiz).where(Quiz.id == quiz_id).with_for_update())
        if quiz is None or quiz.status != "published":
            raise _not_found()
        enrollment = await self._active_enrollment(quiz.course_id, user.id)
        count = int(await self.session.scalar(select(func.count()).select_from(QuizAttempt).where(
            QuizAttempt.quiz_id == quiz.id, QuizAttempt.user_id == user.id,
        )) or 0)
        if quiz.max_attempts is not None and count >= quiz.max_attempts:
            raise ApiError(409, "attempt_limit_reached", "The maximum number of quiz attempts has been reached.")
        questions = await self._questions(quiz.id)
        snapshot = {
            "title": quiz.title, "passing_score_percent": quiz.passing_score_percent,
            "is_required": quiz.is_required,
            "questions": [{
                "id": str(q.id), "question_type": q.question_type, "prompt": q.prompt,
                "options": q.options, "answer_key": q.answer_key,
                "points": str(q.points), "position": q.position,
                "explanation": q.explanation,
            } for q in questions],
        }
        max_score = sum((Decimal(str(q.points)) for q in questions), Decimal(0))
        now = datetime.now(UTC)
        attempt = QuizAttempt(
            quiz_id=quiz.id, user_id=user.id, enrollment_id=enrollment.id,
            quiz_version=quiz.version, snapshot=snapshot, max_score=max_score,
            expires_at=now + timedelta(minutes=quiz.time_limit_minutes) if quiz.time_limit_minutes else None,
        )
        self.session.add(attempt)
        await self.session.flush()
        await self.session.commit()
        return {
            "id": attempt.id, "quiz_id": quiz.id, "quiz_version": quiz.version,
            "questions": [{k: v for k, v in q.items() if k not in {"answer_key", "explanation"}}
                          for q in snapshot["questions"]],
            "expires_at": attempt.expires_at, "started_at": attempt.started_at,
        }

    async def save_answers(self, attempt_id: uuid.UUID, user: User, answers: list[AnswerInput]) -> dict[str, Any]:
        attempt = await self.session.scalar(select(QuizAttempt).where(QuizAttempt.id == attempt_id).with_for_update())
        if attempt is None or attempt.user_id != user.id:
            raise ApiError(404, "attempt_not_found", "Attempt not found.")
        if attempt.status != "in_progress":
            raise ApiError(409, "attempt_already_submitted", "Answers for a submitted attempt are immutable.")
        if attempt.expires_at and datetime.now(UTC) >= attempt.expires_at:
            raise ApiError(409, "attempt_expired", "The quiz time limit has expired.")
        snapshot = {uuid.UUID(q["id"]): q for q in attempt.snapshot["questions"]}
        for item in answers:
            question = snapshot.get(item.question_id)
            if question is None:
                raise ApiError(422, "question_not_in_attempt", "Question does not belong to this attempt.")
            existing = await self.session.scalar(select(QuizAnswer).where(
                QuizAnswer.attempt_id == attempt.id, QuizAnswer.question_key == item.question_id,
            ))
            if existing is None:
                existing = QuizAnswer(attempt_id=attempt.id, question_key=item.question_id, answer=item.answer)
                self.session.add(existing)
            else:
                existing.answer = item.answer
        await self.session.commit()
        return {"saved": len(answers)}

    @staticmethod
    def _is_correct(question: dict[str, Any], answer: Any) -> bool:
        kind, key = question["question_type"], question["answer_key"]
        if kind == "short_text":
            return isinstance(answer, str) and _normalize(answer) in {_normalize(x) for x in key}
        if kind == "true_false":
            return isinstance(answer, bool) and answer is key
        if kind == "single_choice":
            return str(answer) == str(key[0] if isinstance(key, list) else key)
        if kind == "multiple_choice":
            return isinstance(answer, list) and set(map(str, answer)) == set(map(str, key))
        return False

    async def submit(self, attempt_id: uuid.UUID, user: User) -> dict[str, Any]:
        attempt = await self.session.scalar(select(QuizAttempt).where(QuizAttempt.id == attempt_id).with_for_update())
        if attempt is None or attempt.user_id != user.id:
            raise ApiError(404, "attempt_not_found", "Attempt not found.")
        if attempt.status != "in_progress":
            raise ApiError(409, "attempt_already_submitted", "This attempt has already been submitted.")
        answers = list(await self.session.scalars(select(QuizAnswer).where(QuizAnswer.attempt_id == attempt.id)))
        answer_map = {a.question_key: a for a in answers}
        score = Decimal(0)
        for q in attempt.snapshot["questions"]:
            answer = answer_map.get(uuid.UUID(q["id"]))
            correct = bool(answer and self._is_correct(q, answer.answer))
            points = Decimal(str(q["points"])) if correct else Decimal(0)
            if answer:
                answer.is_correct = correct
                answer.awarded_points = points
            score += points
        maximum = Decimal(str(attempt.max_score))
        percent = (score * Decimal(100) / maximum).quantize(Decimal("0.01")) if maximum else Decimal(0)
        passed = percent >= Decimal(str(attempt.snapshot["passing_score_percent"]))
        attempt.score, attempt.percent, attempt.passed = score, percent, passed
        attempt.status = "submitted"
        attempt.completed_at = datetime.now(UTC)
        quiz = await self.session.get(Quiz, attempt.quiz_id)
        course = await self.session.get(Course, quiz.course_id)
        await publish_event(self.session, QuizCompleted(
            user_id=user.id, attempt_id=attempt.id, course_slug=course.slug,
            quiz_title=attempt.snapshot["title"], passed=passed, score=score, max_score=maximum,
        ))
        await ProgressService(self.session).reconcile_course(quiz.course_id)
        await self.session.commit()
        all_attempts = int(await self.session.scalar(select(func.count()).select_from(QuizAttempt).where(
            QuizAttempt.quiz_id == attempt.quiz_id, QuizAttempt.user_id == user.id,
        )) or 1)
        return await self._result(attempt, all_attempts, answers)

    async def history(self, quiz_id: uuid.UUID, user: User) -> list[dict[str, Any]]:
        quiz = await self.session.get(Quiz, quiz_id)
        if quiz is None:
            raise _not_found()
        attempts = list(await self.session.scalars(select(QuizAttempt).where(
            QuizAttempt.quiz_id == quiz.id, QuizAttempt.user_id == user.id,
        ).order_by(QuizAttempt.started_at)))
        results = []
        for index, attempt in enumerate(attempts, start=1):
            answers = list(await self.session.scalars(select(QuizAnswer).where(QuizAnswer.attempt_id == attempt.id)))
            results.append(await self._result(attempt, index, answers))
        return results

    async def _result(self, attempt: QuizAttempt, number: int, answers: list[QuizAnswer]) -> dict[str, Any]:
        questions = {uuid.UUID(q["id"]): q for q in attempt.snapshot["questions"]}
        return {
            "id": attempt.id, "quiz_id": attempt.quiz_id, "quiz_version": attempt.quiz_version,
            "status": attempt.status, "score": attempt.score, "max_score": attempt.max_score,
            "percent": attempt.percent, "passed": attempt.passed, "attempt_number": number,
            "completed_at": attempt.completed_at,
            "answers": [{"question_id": a.question_key, "answer": a.answer,
                         "awarded_points": a.awarded_points, "is_correct": a.is_correct,
                         "explanation": questions.get(a.question_key, {}).get("explanation")}
                        for a in answers],
        }
