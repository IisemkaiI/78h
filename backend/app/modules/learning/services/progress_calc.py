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
    removed_lessons_count: int = 0


def calculate_progress(
    *,
    total_lessons: int,
    completed_lessons: int,
    in_progress_lessons: int,
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
    percent = (completed * 100) // total if total else 0
    return ProgressCounts(
        total_lessons=total,
        completed_lessons=completed,
        in_progress_lessons=in_progress,
        not_started_lessons=not_started,
        progress_percent=percent,
        is_completed=total > 0 and completed == total,
        removed_lessons_count=max(removed_lessons_count, 0),
    )
