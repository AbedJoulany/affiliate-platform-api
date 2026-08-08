from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class DependencyStatus(BaseModel):
    status: Literal["up", "down"]


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[Literal["database", "redis"], DependencyStatus]


class WorkerHealthResponse(BaseModel):
    """Aggregate Celery Beat/worker pipeline liveness (Phase B Task 2)."""

    status: Literal["healthy", "degraded", "unknown"]
    last_heartbeat_at: datetime | None = None
