"""Unit tests for progress arithmetic (no database required)."""

from __future__ import annotations

from app.modules.learning.services.progress_calc import calculate_progress


def test_empty_course_is_zero_and_not_completed() -> None:
    snapshot = calculate_progress(
        total_lessons=0,
        completed_lessons=0,
        in_progress_lessons=0,
    )

    assert snapshot.total_lessons == 0
    assert snapshot.not_started_lessons == 0
    assert snapshot.progress_percent == 0
    assert snapshot.is_completed is False


def test_partial_progress_rounds_down() -> None:
    snapshot = calculate_progress(
        total_lessons=3,
        completed_lessons=2,
        in_progress_lessons=0,
    )

    assert snapshot.progress_percent == 66
    assert snapshot.not_started_lessons == 1
    assert snapshot.is_completed is False


def test_completed_course() -> None:
    snapshot = calculate_progress(
        total_lessons=3,
        completed_lessons=3,
        in_progress_lessons=0,
    )

    assert snapshot.progress_percent == 100
    assert snapshot.not_started_lessons == 0
    assert snapshot.is_completed is True


def test_in_progress_and_removed_lessons() -> None:
    snapshot = calculate_progress(
        total_lessons=4,
        completed_lessons=2,
        in_progress_lessons=1,
        removed_lessons_count=4,
    )

    assert snapshot.not_started_lessons == 1
    assert snapshot.progress_percent == 50
    assert snapshot.removed_lessons_count == 4
    assert snapshot.is_completed is False


def test_counts_are_clamped_for_defensive_reads() -> None:
    snapshot = calculate_progress(
        total_lessons=2,
        completed_lessons=5,
        in_progress_lessons=5,
        removed_lessons_count=-1,
    )

    assert snapshot.completed_lessons == 2
    assert snapshot.in_progress_lessons == 0
    assert snapshot.not_started_lessons == 0
    assert snapshot.progress_percent == 100
    assert snapshot.is_completed is True
    assert snapshot.removed_lessons_count == 0
