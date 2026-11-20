"""FastAPI application entry point.

Run locally with:

    uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import dispose_engine
from app.core.errors import register_exception_handlers
from app.core.events import register_event_handler
from app.modules.notifications.service import handle_notification_event

logger = logging.getLogger(__name__)


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logger.info(
        "Starting %s v%s (env=%s, api=%s)",
        settings.project_name,
        settings.project_version,
        settings.app_env,
        settings.api_v1_prefix,
    )
    logger.info(
        "PostgreSQL target: host=%s port=%s db=%s user=%s (password hidden)",
        settings.postgres_host,
        settings.postgres_port,
        settings.postgres_db,
        settings.postgres_user,
    )
    try:
        yield
    finally:
        await dispose_engine()
        logger.info("Database connections closed")


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()
    register_event_handler(handle_notification_event)
    _configure_logging(settings.log_level)

    application = FastAPI(
        title=settings.project_name,
        version=settings.project_version,
        description="Education Platform — free learning, assessment and certification.",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(application)
    application.include_router(api_router, prefix=settings.api_v1_prefix)

    return application


app = create_app()
