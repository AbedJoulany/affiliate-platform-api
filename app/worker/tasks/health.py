"""Celery Beat/worker pipeline heartbeat (Phase B Task 1).

A successful write proves Beat scheduled this task and a worker executed it
and could reach Redis. It does **not** prove business tasks succeeded, and it
is not an A.2 queue-domain event (no ``queue-events`` / SSE involvement).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from redis import Redis

from app.core.config import get_settings
from app.worker.celery_app import celery_app

# Dedicated Redis key — not a Pub/Sub channel; not ``queue-events``.
WORKER_HEARTBEAT_REDIS_KEY = "celery:health:heartbeat"


def write_worker_heartbeat(
    *,
    redis_client: Any | None = None,
    written_at: datetime | None = None,
) -> dict[str, str | int]:
    """SET the pipeline heartbeat key with TTL. Raises on Redis write failure."""
    settings = get_settings()
    timestamp = written_at or datetime.now(UTC)
    value = timestamp.isoformat()
    ttl_seconds = settings.celery_heartbeat_ttl_seconds

    owns_client = redis_client is None
    client = redis_client or Redis.from_url(settings.broker_url, decode_responses=True)
    try:
        ok = client.set(WORKER_HEARTBEAT_REDIS_KEY, value, ex=ttl_seconds)
        if not ok:
            raise RuntimeError(
                f"Failed to write worker heartbeat key {WORKER_HEARTBEAT_REDIS_KEY!r}"
            )
        return {
            "key": WORKER_HEARTBEAT_REDIS_KEY,
            "written_at": value,
            "ttl_seconds": ttl_seconds,
        }
    finally:
        if owns_client:
            client.close()


@celery_app.task(name="app.worker.tasks.health.worker_heartbeat")
def worker_heartbeat() -> dict[str, str | int]:
    """Beat-scheduled liveness tick — no DB, no external APIs, no A.2 events."""
    return write_worker_heartbeat()
