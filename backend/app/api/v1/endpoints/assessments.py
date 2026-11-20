"""HTTP routes for quizzes, practical assignments and course instructors."""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status

from app.api.deps import SessionDep
from app.modules.assessments.schemas import (
    AnswerInput, AssignmentCreate, AssignmentUpdate, InstructorCreate,
    QuizCreate, QuizUpdate, ReviewInput, SubmissionText,
)
from app.modules.assessments.services.assignments import AssignmentService
from app.modules.assessments.services.quiz import QuizService
from app.modules.auth.dependencies import require_any_permissions, require_permissions
from app.modules.users.models import User
from app.modules.users.rbac import PermissionCode as P

router = APIRouter(prefix="/assessments", tags=["Assessments"])

Author = Annotated[User, Depends(require_any_permissions(P.ASSESSMENTS_MANAGE_OWN, P.ASSESSMENTS_MANAGE_ALL))]
Publisher = Annotated[User, Depends(require_any_permissions(P.ASSESSMENTS_PUBLISH_OWN, P.ASSESSMENTS_MANAGE_ALL))]
Learner = Annotated[User, Depends(require_permissions(P.ASSESSMENTS_ATTEMPT))]
OwnResults = Annotated[User, Depends(require_permissions(P.ASSESSMENTS_READ_OWN_RESULTS))]
Submitter = Annotated[User, Depends(require_permissions(P.ASSESSMENTS_SUBMIT))]
Reviewer = Annotated[User, Depends(require_any_permissions(
    P.ASSESSMENTS_REVIEW, P.ASSESSMENTS_MANAGE_OWN, P.ASSESSMENTS_MANAGE_ALL,
))]
StaffManager = Annotated[User, Depends(require_any_permissions(P.ASSESSMENTS_INSTRUCTORS_MANAGE, P.ASSESSMENTS_MANAGE_ALL))]


@router.post("/quizzes", status_code=status.HTTP_201_CREATED)
async def create_quiz(payload: QuizCreate, user: Author, session: SessionDep):
    return await QuizService(session).create(user, payload)


@router.get("/courses/{course_id}/quizzes")
async def list_course_quizzes(course_id: uuid.UUID, user: Author, session: SessionDep):
    return await QuizService(session).list_for_course(course_id, user)


@router.get("/quizzes/{quiz_id}")
async def read_quiz(quiz_id: uuid.UUID, user: Author, session: SessionDep):
    return await QuizService(session).get_author(quiz_id, user)


@router.patch("/quizzes/{quiz_id}")
async def update_quiz(quiz_id: uuid.UUID, payload: QuizUpdate, user: Author, session: SessionDep):
    return await QuizService(session).update(quiz_id, user, payload)


@router.post("/quizzes/{quiz_id}/publish")
async def publish_quiz(quiz_id: uuid.UUID, user: Publisher, session: SessionDep):
    return await QuizService(session).set_status(quiz_id, user, "published")


@router.post("/quizzes/{quiz_id}/unpublish")
async def unpublish_quiz(quiz_id: uuid.UUID, user: Publisher, session: SessionDep):
    return await QuizService(session).set_status(quiz_id, user, "draft")


@router.post("/quizzes/{quiz_id}/archive")
async def archive_quiz(quiz_id: uuid.UUID, user: Publisher, session: SessionDep):
    return await QuizService(session).set_status(quiz_id, user, "archived")


@router.post("/quizzes/{quiz_id}/attempts", status_code=status.HTTP_201_CREATED)
async def start_quiz(quiz_id: uuid.UUID, user: Learner, session: SessionDep):
    return await QuizService(session).start(quiz_id, user)


@router.put("/attempts/{attempt_id}/answers")
async def save_quiz_answers(attempt_id: uuid.UUID, answers: list[AnswerInput], user: Learner, session: SessionDep):
    return await QuizService(session).save_answers(attempt_id, user, answers)


@router.post("/attempts/{attempt_id}/submit")
async def submit_quiz(attempt_id: uuid.UUID, user: Learner, session: SessionDep):
    return await QuizService(session).submit(attempt_id, user)


@router.get("/quizzes/{quiz_id}/attempts/mine")
async def quiz_history(quiz_id: uuid.UUID, user: OwnResults, session: SessionDep):
    return await QuizService(session).history(quiz_id, user)


@router.post("/assignments", status_code=status.HTTP_201_CREATED)
async def create_assignment(payload: AssignmentCreate, user: Author, session: SessionDep):
    return await AssignmentService(session).create(user, payload)


@router.get("/courses/{course_id}/assignments")
async def list_course_assignments(course_id: uuid.UUID, user: Reviewer, session: SessionDep):
    return await AssignmentService(session).list_for_course(course_id, user)


@router.get("/teaching")
async def list_teaching_courses(user: Reviewer, session: SessionDep):
    return await AssignmentService(session).list_teaching_courses(user)


@router.patch("/assignments/{assignment_id}")
async def update_assignment(assignment_id: uuid.UUID, payload: AssignmentUpdate, user: Author, session: SessionDep):
    return await AssignmentService(session).update(assignment_id, user, payload)


@router.post("/assignments/{assignment_id}/publish")
async def publish_assignment(assignment_id: uuid.UUID, user: Publisher, session: SessionDep):
    return await AssignmentService(session).set_status(assignment_id, user, "published")


@router.post("/assignments/{assignment_id}/unpublish")
async def unpublish_assignment(assignment_id: uuid.UUID, user: Publisher, session: SessionDep):
    return await AssignmentService(session).set_status(assignment_id, user, "draft")


@router.post("/assignments/{assignment_id}/archive")
async def archive_assignment(assignment_id: uuid.UUID, user: Publisher, session: SessionDep):
    return await AssignmentService(session).set_status(assignment_id, user, "archived")


@router.put("/assignments/{assignment_id}/submission/draft")
async def save_assignment_draft(assignment_id: uuid.UUID, payload: SubmissionText, user: Submitter, session: SessionDep):
    row = await AssignmentService(session).save_draft(assignment_id, user, payload.response_text)
    return await AssignmentService(session)._submission_dict(row)


@router.post("/assignments/{assignment_id}/submission/submit")
async def submit_assignment(assignment_id: uuid.UUID, user: Submitter, session: SessionDep):
    row = await AssignmentService(session).submit(assignment_id, user)
    return await AssignmentService(session)._submission_dict(row)


@router.get("/assignments/{assignment_id}/submission/mine")
async def own_assignment_submission(assignment_id: uuid.UUID, user: OwnResults, session: SessionDep):
    return await AssignmentService(session).own_submission(assignment_id, user)


@router.get("/assignments/{assignment_id}/submissions")
async def list_assignment_submissions(assignment_id: uuid.UUID, user: Reviewer, session: SessionDep):
    return await AssignmentService(session).list_submissions(assignment_id, user)


@router.post("/submissions/{submission_id}/start-review")
async def start_review(submission_id: uuid.UUID, user: Reviewer, session: SessionDep):
    return await AssignmentService(session).mark_under_review(submission_id, user)


@router.post("/submissions/{submission_id}/review")
async def review_submission(submission_id: uuid.UUID, payload: ReviewInput, user: Reviewer, session: SessionDep):
    return await AssignmentService(session).review(submission_id, user, payload)


@router.get("/courses/{course_id}/instructors")
async def list_course_instructors(course_id: uuid.UUID, user: StaffManager, session: SessionDep):
    return await AssignmentService(session).list_instructors(course_id, user)


@router.post("/courses/{course_id}/instructors", status_code=status.HTTP_201_CREATED)
async def add_course_instructor(course_id: uuid.UUID, payload: InstructorCreate, user: StaffManager, session: SessionDep):
    row = await AssignmentService(session).add_instructor(course_id, user, payload.instructor_id)
    return {"course_id": row.course_id, "instructor_id": row.instructor_id,
            "assigned_by_id": row.assigned_by_id, "created_at": row.created_at}


@router.delete("/courses/{course_id}/instructors/{instructor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_course_instructor(course_id: uuid.UUID, instructor_id: uuid.UUID, user: StaffManager, session: SessionDep):
    await AssignmentService(session).remove_instructor(course_id, instructor_id, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
