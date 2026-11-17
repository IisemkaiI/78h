"""Response models for the service (system) endpoints."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"] = Field(description="Process is running and able to answer requests.")
    service: str = Field(description="Service identifier.")
    version: str = Field(description="Project version.")
    environment: str = Field(description="Deployment environment name.")


class DatabaseStatus(BaseModel):
    status: Literal["available", "unavailable"] = Field(
        description="Result of a live `SELECT 1` probe against PostgreSQL."
    )
    detail: str | None = Field(
        default=None,
        description="Short, non-sensitive failure category. No hosts, users or passwords.",
    )
    latency_ms: float | None = Field(
        default=None, description="Probe round-trip time in milliseconds."
    )


class ReadyResponse(BaseModel):
    status: Literal["ready", "not_ready"] = Field(
        description="`ready` only when every dependency check passed."
    )
    version: str = Field(description="Project version.")
    database: DatabaseStatus = Field(description="PostgreSQL dependency status.")


class InfoResponse(BaseModel):
    application: str = Field(description="Human readable application name.")
    version: str = Field(description="Project version.")
    environment: str = Field(description="Deployment environment name.")
    api_version: str = Field(description="Versioned API prefix currently served.")


class ErrorBody(BaseModel):
    code: str
    message: str
    details: object | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody
