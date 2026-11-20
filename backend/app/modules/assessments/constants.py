"""Stable assessment state vocabulary."""

QUIZ_STATUSES = ("draft", "published", "archived")
QUESTION_TYPES = ("single_choice", "multiple_choice", "true_false", "short_text")
ATTEMPT_STATUSES = ("in_progress", "submitted")
ASSIGNMENT_STATUSES = ("draft", "published", "archived")
SUBMISSION_STATUSES = (
    "draft", "submitted", "under_review", "revision_required", "graded"
)
REVIEW_DECISIONS = ("accepted", "revision_required")
