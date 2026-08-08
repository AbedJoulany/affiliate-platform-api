"""Worker/Beat pipeline health check (Phase B Task 2).

Reads the Task 1 Redis heartbeat key only. Does not call Celery control
commands, write Redis, or alter ``/ready`` / ``/health``.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from redis import asyncio as redis

from app.core.config import Settings, get_settings
from app.schemas.health import WorkerHealthResponse
from app.worker.tasks.health import WORKER_HEARTBEAT_REDIS_KEY

logger = logging.getLogger(__name__)


class WorkerHealthService:
    """Evaluate Celery Beat→worker pipeline liveness from the heartbeat key."""

    CHECK_TIMEOUT_SECONDS = 2.0

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    async def check(self) -> WorkerHealthResponse:
        raw: str | bytes | None
        try:
            raw = await self._get_heartbeat_value()
        except Exception:
            logger.exception("Worker health Redis read failed")
            return WorkerHealthResponse(status="unknown", last_heartbeat_at=None)

        if raw is None:
            return WorkerHealthResponse(status="degraded", last_heartbeat_at=None)

        if isinstance(raw, bytes):
            try:
                raw = raw.decode("utf-8")
            except UnicodeDecodeError:
                logger.warning("Worker heartbeat value is not valid UTF-8")
                return WorkerHealthResponse(status="unknown", last_heartbeat_at=None)

        try:
            last_seen = datetime.fromisoformat(raw)
        except ValueError:
            logger.warning("Worker heartbeat value is not a valid ISO timestamp")
            return WorkerHealthResponse(status="unknown", last_heartbeat_at=None)

        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=UTC)

        age_seconds = (datetime.now(UTC) - last_seen).total_seconds()
        ttl_seconds = self.settings.celery_heartbeat_ttl_seconds
        if age_seconds < 0 or age_seconds > ttl_seconds:
            return WorkerHealthResponse(status="degraded", last_heartbeat_at=last_seen)

        return WorkerHealthResponse(status="healthy", last_heartbeat_at=last_seen)

    async def _get_heartbeat_value(self) -> str | bytes | None:
        client = None
        try:
            client = redis.from_url(
                self.settings.broker_url,
                socket_connect_timeout=self.CHECK_TIMEOUT_SECONDS,
                socket_timeout=self.CHECK_TIMEOUT_SECONDS,
                decode_responses=True,
            )
            async with asyncio.timeout(self.CHECK_TIMEOUT_SECONDS):
                return await client.get(WORKER_HEARTBEAT_REDIS_KEY)
        finally:
            if client is not None:
                try:
                    async with asyncio.timeout(self.CHECK_TIMEOUT_SECONDS):
                        await client.aclose()
                except Exception:
                    pass
