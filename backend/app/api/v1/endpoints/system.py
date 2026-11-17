"""Service endpoints: liveness, readiness and build info."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Response, status

from app.api.v1.schemas import (
    DatabaseStatus,
    ErrorResponse,
    HealthResponse,
    InfoResponse,
    ReadyResponse,
)
from app.core.config import get_settings
from app.core.database import DatabaseUnavailableError, ping_database

logger = logging.getLogger(__name__)
router = APIRouter(tags=["System"])

settings = get_settings()

_ERROR_RESPONSES = {503: {"model": ErrorResponse, "description": "Dependency unavailable"}}


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness probe",
    description="Confirms that the API process is up. Does not touch the database.",
)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="education-platform-api",
        version=settings.project_version,
        environment=settings.app_env,
    )


@router.get(
    "/ready",
    response_model=ReadyResponse,
    summary="Readiness probe",
    description=(
        "Checks that the API can serve traffic: performs a live `SELECT 1` "
        "against PostgreSQL. Returns 503 when the database is unreachable."
    ),
    responses=_ERROR_RESPONSES,
)
async def ready(response: Response) -> ReadyResponse:
    try:
        latency_ms = await ping_database()
    except DatabaseUnavailableError as exc:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadyResponse(
            status="not_ready",
            version=settings.project_version,
            database=DatabaseStatus(status="unavailable", detail=str(exc) or "connection failed"),
        )

    return ReadyResponse(
        status="ready",
        version=settings.project_version,
        database=DatabaseStatus(
            status="available", detail=None, latency_ms=round(latency_ms, 2)
        ),
    )


@router.get(
    "/info",
    response_model=InfoResponse,
    summary="Application info",
    description="Application name and project version. Contains no secrets.",
)
async def info() -> InfoResponse:
    return InfoResponse(
        application=settings.project_name,
        version=settings.project_version,
        environment=settings.app_env,
        api_version=settings.api_v1_prefix,
    )
