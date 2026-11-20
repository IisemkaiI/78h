from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import ApplicationEvent, AssignmentReviewed, CertificateIssued, CourseCompleted, QuizCompleted
from app.modules.notifications.models import Notification


async def handle_notification_event(session: AsyncSession, event: ApplicationEvent) -> None:
    if isinstance(event, CourseCompleted):
        kind, title, body = "course_completed", "Курс завершён", f"Вы завершили курс «{event.course_title}»."
        key, payload = f"course_completed:{event.enrollment_id}:{event.completed_at}", {"enrollment_id": str(event.enrollment_id), "course_slug": event.course_slug}
    elif isinstance(event, QuizCompleted):
        kind = "quiz_completed"
        title = "Попытка теста завершена"
        body = f"Тест «{event.quiz_title}»: {event.score:g} из {event.max_score:g} баллов. " + ("Тест пройден." if event.passed else "Тест не пройден.")
        key = f"quiz_completed:{event.attempt_id}"
        payload = {"attempt_id": str(event.attempt_id), "course_slug": event.course_slug, "passed": event.passed, "score": str(event.score), "max_score": str(event.max_score)}
    elif isinstance(event, AssignmentReviewed):
        accepted = event.decision == "accepted"
        kind = "assignment_accepted" if accepted else "assignment_revision_required"
        title = "Практическая работа принята" if accepted else "Практическая работа возвращена на доработку"
        body = f"Задание «{event.assignment_title}» проверено." + (f" Оценка: {event.score:g}." if event.score is not None else "")
        key = f"assignment_review:{event.submission_id}:v{event.version_number}:{event.decision}"
        payload = {"submission_id": str(event.submission_id), "course_slug": event.course_slug, "version": event.version_number}
    elif isinstance(event, CertificateIssued):
        kind, title, body = "certificate_issued", "Сертификат выдан", f"Вы получили сертификат за курс «{event.course_title}»."
        key, payload = f"certificate_issued:{event.certificate_id}", {"certificate_id": str(event.certificate_id), "certificate_number": event.certificate_number}
    else:
        raise TypeError(f"Unsupported application event: {type(event)!r}")
    statement = insert(Notification).values(
        id=uuid.uuid4(), user_id=event.user_id, type=kind, title=title, body=body,
        payload=payload, source_event_key=key,
    ).on_conflict_do_nothing(constraint="uq_notifications_user_event")
    await session.execute(statement)


class NotificationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list(self, user_id: uuid.UUID, page: int, page_size: int, unread_only: bool):
        base = select(Notification).where(Notification.user_id == user_id)
        if unread_only:
            base = base.where(Notification.read_at.is_(None))
        total = int(await self.session.scalar(select(func.count()).select_from(base.subquery())) or 0)
        unread_count = int(await self.session.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == user_id, Notification.read_at.is_(None))) or 0)
        items = list((await self.session.scalars(base.order_by(Notification.created_at.desc(), Notification.id.desc()).offset((page - 1) * page_size).limit(page_size))).all())
        return {"items": items, "total": total, "unread_count": unread_count, "page": page, "page_size": page_size}

    async def unread_count(self, user_id: uuid.UUID) -> int:
        return int(await self.session.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == user_id, Notification.read_at.is_(None))) or 0)

    async def mark_read(self, user_id: uuid.UUID, notification_id: uuid.UUID):
        row = await self.session.scalar(select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id).with_for_update())
        if row is None:
            return None
        if row.read_at is None:
            row.read_at = datetime.now(UTC)
            await self.session.commit()
        return row

    async def mark_all_read(self, user_id: uuid.UUID) -> int:
        result = await self.session.execute(update(Notification).where(Notification.user_id == user_id, Notification.read_at.is_(None)).values(read_at=datetime.now(UTC)))
        await self.session.commit()
        return result.rowcount or 0
