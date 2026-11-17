"""Tests for GET /api/v1/info."""

from __future__ import annotations

from httpx import AsyncClient

from app.core.config import get_settings


async def test_info_returns_application_name_and_version(client: AsyncClient) -> None:
    response = await client.get("/api/v1/info")

    assert response.status_code == 200
    payload = response.json()
    settings = get_settings()
    assert payload["application"] == settings.project_name
    assert payload["version"] == settings.project_version
    assert payload["api_version"] == "/api/v1"


async def test_info_does_not_leak_credentials(client: AsyncClient) -> None:
    response = await client.get("/api/v1/info")

    body = response.text.lower()
    assert "password" not in body
    assert "asyncpg" not in body
    assert "postgres" not in body
