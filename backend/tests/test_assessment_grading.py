"""Pure Sprint 5 grading and progress calculations."""

import pytest

from app.modules.assessments.services.quiz import QuizService
from app.modules.learning.services.progress_calc import calculate_progress


@pytest.mark.parametrize(
    ("kind", "key", "answer", "correct"),
    [
        ("single_choice", "a", "a", True),
        ("single_choice", "a", "b", False),
        ("multiple_choice", ["a", "b"], ["b", "a"], True),
        ("multiple_choice", ["a", "b"], ["a"], False),
        ("true_false", True, True, True),
        ("true_false", False, True, False),
        ("short_text", ["Python", "Пайтон"], "  PYTHON ", True),
        ("short_text", ["Python"], "Py thon", False),
    ],
)
def test_question_types_are_checked_server_side(kind, key, answer, correct) -> None:
    assert QuizService._is_correct({"question_type": kind, "answer_key": key}, answer) is correct


def test_required_assessments_participate_in_course_completion_and_percent() -> None:
    progress = calculate_progress(
        total_lessons=2,
        completed_lessons=2,
        in_progress_lessons=0,
        total_required_assessments=2,
        completed_required_assessments=1,
    )
    assert progress.progress_percent == 75
    assert progress.is_completed is False
    assert progress.total_required_assessments == 2
    assert progress.completed_required_assessments == 1


def test_failed_required_check_does_not_complete_course() -> None:
    progress = calculate_progress(
        total_lessons=1,
        completed_lessons=1,
        in_progress_lessons=0,
        total_required_assessments=1,
        completed_required_assessments=0,
    )
    assert progress.progress_percent == 50
    assert progress.is_completed is False


def test_course_can_complete_from_only_required_assessments() -> None:
    progress = calculate_progress(
        total_lessons=0,
        completed_lessons=0,
        in_progress_lessons=0,
        total_required_assessments=2,
        completed_required_assessments=2,
    )
    assert progress.progress_percent == 100
    assert progress.is_completed is True
