"""Phase A.2 real-time event payload schemas.

Versioned SSE/Redis envelope plus one ``data`` model per queue event in the
Phase A.2 catalog. Schemas only — no publishing, persistence, or transport.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import QueueStatus

# Canonical event names (§2). Keep exact strings — clients and producers share them.
QUEUE_STATUS_CHANGED = "queue.status_changed"
QUEUE_DELETED = "queue.deleted"
QUEUE_ATTEMPT_STARTED = "queue.attempt_started"
QUEUE_ATTEMPT_SUCCEEDED = "queue.attempt_succeeded"
QUEUE_ATTEMPT_FAILED = "queue.attempt_failed"

EVENT_ENVELOPE_VERSION = 1


class QueueEventEnvelope(BaseModel):
    """Versioned envelope shared by every Phase A.2 queue event.

    ``data`` holds the event-specific payload (see models below). ``workspace_id``
    is the owning workspace of the QueueItem that produced the event, or ``null``
    for rows that have not been assigned a workspace (Stage-1 nullable column).
    """

    model_config = ConfigDict(extra="forbid")

    event: str = Field(description="Canonical domain-dot-action event name")
    version: int = Field(default=EVENT_ENVELOPE_VERSION, ge=1)
    id: str = Field(description="Stream cursor id (ULID), not a database PK")
    occurred_at: datetime
    workspace_id: str | None = None
    queue_id: UUID
    data: dict[str, Any]


class QueueStatusChangedData(BaseModel):
    """Payload for ``queue.status_changed``."""

    model_config = ConfigDict(extra="forbid")

    queue_id: UUID
    status: QueueStatus
    previous_status: QueueStatus
    scheduled_at: datetime | None = None
    published_at: datetime | None = None


class QueueDeletedData(BaseModel):
    """Payload for ``queue.deleted``."""

    model_config = ConfigDict(extra="forbid")

    queue_id: UUID


class QueueAttemptStartedData(BaseModel):
    """Payload for ``queue.attempt_started``."""

    model_config = ConfigDict(extra="forbid")

    queue_id: UUID
    attempt_number: int = Field(ge=1)
    provider: str


class QueueAttemptSucceededData(BaseModel):
    """Payload for ``queue.attempt_succeeded``."""

    model_config = ConfigDict(extra="forbid")

    queue_id: UUID
    attempt_number: int = Field(ge=1)
    provider_message_id: int


class QueueAttemptFailedData(BaseModel):
    """Payload for ``queue.attempt_failed``."""

    model_config = ConfigDict(extra="forbid")

    queue_id: UUID
    attempt_number: int = Field(ge=1)
    error_code: str
    is_terminal: bool
