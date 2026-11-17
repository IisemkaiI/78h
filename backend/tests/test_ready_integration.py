"""GET /api/v1/ready against a real PostgreSQL.

Marked `integration`: requires the database container to be running
(`docker compose up -d postgres`). These tests are excluded from the default
run through `pytest.ini` addopts and are executed with `pytest -m integration`.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.core.database import ping_database


@pytest.mark.integration
async def test_database_is_reachable() -> None:
    latency_ms = await ping_database()

    assert latency_ms >= 0


@pytest.mark.integration
async def test_ready_reports_database_available(client: AsyncClient) -> None:
    response = await client.get("/api/v1/ready")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ready"
    assert payload["database"]["status"] == "available"
    assert payload["database"]["detail"] is None
    assert payload["database"]["latency_ms"] is not None
