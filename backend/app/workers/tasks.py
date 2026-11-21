"""Bounded background work scheduled by Celery Beat."""
from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from celery import shared_task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionFactory
from app.modules.learning.models.enrollment import Enrollment
from app.modules.organizations.models import OrganizationCourseAssignment

logger = logging.getLogger(__name__)


async def mark_overdue_assignments(session: AsyncSession) -> int:
    """Persist an overdue marker for accepted, incomplete assignments past due."""
    now = datetime.now(UTC)
    rows = list((await session.scalars(
        select(OrganizationCourseAssignment)
        .join(Enrollment, Enrollment.id == OrganizationCourseAssignment.enrollment_id)
        .where(
            OrganizationCourseAssignment.status == "accepted",
            OrganizationCourseAssignment.due_at.is_not(None),
            OrganizationCourseAssignment.due_at < now,
            OrganizationCourseAssignment.overdue_at.is_(None),
            Enrollment.completed_at.is_(None),
        )
        .order_by(OrganizationCourseAssignment.id)
        .with_for_update(skip_locked=True)
    )).all())
    for assignment in rows:
        assignment.overdue_at = now
    await session.commit()
    logger.info("Marked %d corporate assignments overdue at %s", len(rows), now.isoformat())
    return len(rows)


@shared_task(
    bind=True,
    name="app.workers.tasks.mark_overdue_assignments",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=3,
)
def mark_overdue_assignments_task(_task) -> int:
    """Celery sync entrypoint; each execution owns its async DB session."""
    try:
        async def execute() -> int:
            async with SessionFactory() as session:
                return await mark_overdue_assignments(session)

        return asyncio.run(execute())
    except Exception:
        logger.exception("Failed to mark overdue corporate assignments")
        raise
