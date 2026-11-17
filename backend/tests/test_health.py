"""Tests for GET /api/v1/health — must not depend on the database."""

from __future__ import annotations

from httpx import AsyncClient


async def test_health_returns_ok(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "education-platform-api"
    assert payload["version"]
    assert payload["environment"]


async def test_health_exposes_no_connection_details(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    body = response.text.lower()
    for forbidden in ("password", "postgresql://", "asyncpg://", "5432", "secret"):
        assert forbidden not in body
