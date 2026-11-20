"""Small synchronous, typed application event dispatcher.

Events are handled in the publisher's SQLAlchemy session before commit. This is
an in-process integration contract, not a queue or durable event bus.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Awaitable, Callable, TypeAlias

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class CourseCompleted:
    user_id: uuid.UUID
    enrollment_id: uuid.UUID
    course_slug: str
    course_title: str
    completed_at: str


@dataclass(frozen=True, slots=True)
class QuizCompleted:
    user_id: uuid.UUID
    attempt_id: uuid.UUID
    course_slug: str
    quiz_title: str
    passed: bool
    score: Decimal
    max_score: Decimal


@dataclass(frozen=True, slots=True)
class AssignmentReviewed:
    user_id: uuid.UUID
    submission_id: uuid.UUID
    version_number: int
    course_slug: str
    assignment_title: str
    decision: str
    score: Decimal | None


@dataclass(frozen=True, slots=True)
class CertificateIssued:
    user_id: uuid.UUID
    certificate_id: uuid.UUID
    course_title: str
    certificate_number: str


ApplicationEvent: TypeAlias = CourseCompleted | QuizCompleted | AssignmentReviewed | CertificateIssued
EventHandler = Callable[[AsyncSession, ApplicationEvent], Awaitable[None]]
_handlers: list[EventHandler] = []


def register_event_handler(handler: EventHandler) -> None:
    if handler not in _handlers:
        _handlers.append(handler)


async def publish_event(session: AsyncSession, event: ApplicationEvent) -> None:
    for handler in tuple(_handlers):
        await handler(session, event)
