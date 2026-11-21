"""FastAPI application entry point.

Run locally with:

    uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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


def _mount_frontend(application: FastAPI, dist_dir: Path | None, api_prefix: str) -> None:
    """Serve a compiled SPA build with a history-API fallback.

    The mobile/Amvera deployment ships the React bundle inside the API image.
    API routes are registered first, so this catch-all only receives unknown
    paths; they must return 404 for the API namespace and index.html for SPA
    routes such as ``/courses/python``.
    """
    if dist_dir is None:
        return

    dist = dist_dir.resolve()
    index_file = dist / "index.html"
    if not dist.is_dir() or not index_file.is_file():
        logger.warning("FRONTEND_DIST_DIR=%s has no index.html; serving the API only", dist)
        return

    assets_dir = dist / "assets"
    if assets_dir.is_dir():
        application.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    normalized_prefix = api_prefix.rstrip("/")
    reserved_paths = {"/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"}

    @application.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:
        request_path = f"/{full_path}"
        if (
            request_path == normalized_prefix
            or request_path.startswith(f"{normalized_prefix}/")
            or request_path in reserved_paths
        ):
            raise HTTPException(status_code=404, detail="Not found")

        candidate = (dist / full_path).resolve()
        if full_path and candidate.is_file() and dist in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index_file)

    logger.info("Serving compiled SPA from %s", dist)


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
    _mount_frontend(application, settings.frontend_dist_dir, settings.api_v1_prefix)

    return application


app = create_app()
