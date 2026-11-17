"""Tests for the unified error envelope."""

from __future__ import annotations

from httpx import AsyncClient


async def test_unknown_route_returns_structured_error(client: AsyncClient) -> None:
    response = await client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    payload = response.json()
    assert payload["error"]["code"] == "not_found"
    assert payload["error"]["message"]


async def test_unsupported_method_returns_structured_error(client: AsyncClient) -> None:
    response = await client.post("/api/v1/health")

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"
