"""Tests for Phase B Task 2 — GET /worker/health."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.core.config import get_settings
from app.schemas.health import ReadinessResponse
from app.worker.tasks.health import WORKER_HEARTBEAT_REDIS_KEY


@pytest.mark.asyncio
async def test_health_check_unchanged(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_worker_health_fresh_heartbeat(client):
    now = datetime.now(UTC)
    with patch(
        "app.services.worker_health.WorkerHealthService._get_heartbeat_value",
        new=AsyncMock(return_value=now.isoformat()),
    ):
        response = await client.get("/worker/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["last_heartbeat_at"] is not None
    assert datetime.fromisoformat(body["last_heartbeat_at"]) == now


@pytest.mark.asyncio
async def test_worker_health_missing_heartbeat(client):
    with patch(
        "app.services.worker_health.WorkerHealthService._get_heartbeat_value",
        new=AsyncMock(return_value=None),
    ):
        response = await client.get("/worker/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["last_heartbeat_at"] is None


@pytest.mark.asyncio
async def test_worker_health_stale_heartbeat(client):
    ttl = get_settings().celery_heartbeat_ttl_seconds
    stale = datetime.now(UTC) - timedelta(seconds=ttl + 5)
    with patch(
        "app.services.worker_health.WorkerHealthService._get_heartbeat_value",
        new=AsyncMock(return_value=stale.isoformat()),
    ):
        response = await client.get("/worker/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert datetime.fromisoformat(body["last_heartbeat_at"]) == stale


@pytest.mark.asyncio
async def test_worker_health_redis_failure(client):
    with patch(
        "app.services.worker_health.WorkerHealthService._get_heartbeat_value",
        new=AsyncMock(side_effect=ConnectionError("redis down")),
    ):
        response = await client.get("/worker/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "unknown"
    assert body["last_heartbeat_at"] is None
    assert "ConnectionError" not in response.text
    assert "traceback" not in response.text.lower()


@pytest.mark.asyncio
async def test_worker_health_invalid_timestamp(client):
    with patch(
        "app.services.worker_health.WorkerHealthService._get_heartbeat_value",
        new=AsyncMock(return_value="not-a-timestamp"),
    ):
        response = await client.get("/worker/health")

    assert response.status_code == 503
    assert response.status_code != 500
    body = response.json()
    assert body["status"] == "unknown"
    assert body["last_heartbeat_at"] is None


@pytest.mark.asyncio
async def test_worker_health_route_is_root_not_api_v1(client):
    with patch(
        "app.services.worker_health.WorkerHealthService._get_heartbeat_value",
        new=AsyncMock(return_value=None),
    ):
        root = await client.get("/worker/health")
        prefixed = await client.get("/api/v1/worker/health")

    assert root.status_code == 503
    assert prefixed.status_code == 404


@pytest.mark.asyncio
async def test_readiness_response_schema_unchanged():
    """Guard: worker health must not widen ReadinessResponse.checks."""
    fields = ReadinessResponse.model_fields
    assert "checks" in fields
    # Instantiation with only database/redis remains valid.
    readiness = ReadinessResponse(
        status="ready",
        checks={
            "database": {"status": "up"},
            "redis": {"status": "up"},
        },
    )
    assert set(readiness.checks) == {"database", "redis"}


def test_heartbeat_key_constant_unchanged():
    assert WORKER_HEARTBEAT_REDIS_KEY == "celery:health:heartbeat"
