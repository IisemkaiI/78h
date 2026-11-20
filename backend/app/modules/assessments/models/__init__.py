"""Importing this package registers assessment tables on Base.metadata."""

from app.modules.assessments.models.core import (
    AssignmentReview,
    AssignmentSubmission,
    CourseInstructor,
    PracticalAssignment,
    Quiz,
    QuizAnswer,
    QuizAttempt,
    QuizQuestion,
    SubmissionVersion,
)

__all__ = [
    "AssignmentReview", "AssignmentSubmission", "CourseInstructor",
    "PracticalAssignment", "Quiz", "QuizAnswer", "QuizAttempt",
    "QuizQuestion", "SubmissionVersion",
]
