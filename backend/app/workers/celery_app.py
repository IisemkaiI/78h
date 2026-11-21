"""Celery app used by Linux worker and beat containers."""
import os

from celery import Celery

app = Celery(
    "education_platform",
    broker=os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0"),
    include=["app.workers.tasks"],
)
app.conf.update(
    result_backend=os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1"),
    timezone="UTC",
    enable_utc=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=300,
    task_time_limit=360,
    beat_schedule={
        "mark-overdue-corporate-assignments-every-15-minutes": {
            "task": "app.workers.tasks.mark_overdue_assignments",
            "schedule": 900.0,
        },
    },
)
