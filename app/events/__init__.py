"""Phase A.2 real-time event package.

B1 ships schemas only. Publisher / SSE transport arrive in later tasks.
"""

from app.events.schemas import (
    EVENT_ENVELOPE_VERSION,
    QUEUE_ATTEMPT_FAILED,
    QUEUE_ATTEMPT_STARTED,
    QUEUE_ATTEMPT_SUCCEEDED,
    QUEUE_DELETED,
    QUEUE_STATUS_CHANGED,
    QueueAttemptFailedData,
    QueueAttemptStartedData,
    QueueAttemptSucceededData,
    QueueDeletedData,
    QueueEventEnvelope,
    QueueStatusChangedData,
)

__all__ = [
    "EVENT_ENVELOPE_VERSION",
    "QUEUE_ATTEMPT_FAILED",
    "QUEUE_ATTEMPT_STARTED",
    "QUEUE_ATTEMPT_SUCCEEDED",
    "QUEUE_DELETED",
    "QUEUE_STATUS_CHANGED",
    "QueueAttemptFailedData",
    "QueueAttemptStartedData",
    "QueueAttemptSucceededData",
    "QueueDeletedData",
    "QueueEventEnvelope",
    "QueueStatusChangedData",
]
