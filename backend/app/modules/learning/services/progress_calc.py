"""Pure progress arithmetic, kept separate from database access for unit tests."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProgressCounts:
    total_lessons: int
    completed_lessons: int
    in_progress_lessons: int
    not_started_lessons: int
    progress_percent: int
    is_completed: bool
    total_required_assessments: int = 0
    completed_required_assessments: int = 0
    removed_lessons_count: int = 0


def calculate_progress(
    *,
    total_lessons: int,
    completed_lessons: int,
    in_progress_lessons: int,
    total_required_assessments: int = 0,
    completed_required_assessments: int = 0,
    removed_lessons_count: int = 0,
) -> ProgressCounts:
    """Build a consistent snapshot from current lessons only.

    Removed lessons are deliberately excluded from the denominator: they are
    history, not part of the current course programme. Counts are clamped so a
    stale row can never produce a negative "not started" value or >100%.
    """
    total = max(total_lessons, 0)
    completed = max(0, min(completed_lessons, total))
    in_progress = max(0, min(in_progress_lessons, total - completed))
    not_started = max(total - completed - in_progress, 0)
    required_total = max(total_required_assessments, 0)
    required_completed = max(0, min(completed_required_assessments, required_total))
    total_items = total + required_total
    completed_items = completed + required_completed
    percent = (completed_items * 100) // total_items if total_items else 0
    return ProgressCounts(
        total_lessons=total,
        completed_lessons=completed,
        in_progress_lessons=in_progress,
        not_started_lessons=not_started,
        progress_percent=percent,
        is_completed=total_items > 0 and completed_items == total_items,
        total_required_assessments=required_total,
        completed_required_assessments=required_completed,
        removed_lessons_count=max(removed_lessons_count, 0),
    )
