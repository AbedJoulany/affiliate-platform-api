"""Minimal unit tests for Phase A.2 event payload schemas (Task B1)."""

from datetime import UTC, datetime
from uuid import uuid4

from app.core.enums import QueueStatus
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


def test_queue_event_envelope_round_trip():
    queue_id = uuid4()
    occurred_at = datetime(2026, 8, 7, 9, 40, 12, 483000, tzinfo=UTC)
    payload = {
        "event": QUEUE_ATTEMPT_FAILED,
        "version": EVENT_ENVELOPE_VERSION,
        "id": "01J9Z8H5F9T4S1R7D8P2K3M4N5",
        "occurred_at": occurred_at,
        "workspace_id": None,
        "queue_id": queue_id,
        "data": {
            "queue_id": str(queue_id),
            "attempt_number": 3,
            "error_code": "dead_letter",
            "is_terminal": True,
        },
    }

    envelope = QueueEventEnvelope.model_validate(payload)
    dumped = envelope.model_dump(mode="json")

    assert dumped["event"] == QUEUE_ATTEMPT_FAILED
    assert dumped["version"] == 1
    assert dumped["id"] == "01J9Z8H5F9T4S1R7D8P2K3M4N5"
    assert dumped["workspace_id"] is None
    assert dumped["queue_id"] == str(queue_id)
    assert dumped["data"]["is_terminal"] is True
    assert QueueEventEnvelope.model_validate(dumped).event == QUEUE_ATTEMPT_FAILED


def test_queue_status_changed_data_validates():
    queue_id = uuid4()
    data = QueueStatusChangedData(
        queue_id=queue_id,
        status=QueueStatus.PUBLISHED,
        previous_status=QueueStatus.QUEUED,
        scheduled_at=None,
        published_at=datetime(2026, 8, 7, 10, 0, tzinfo=UTC),
    )
    dumped = data.model_dump(mode="json")
    assert dumped == {
        "queue_id": str(queue_id),
        "status": "published",
        "previous_status": "queued",
        "scheduled_at": None,
        "published_at": "2026-08-07T10:00:00Z",
    }
    assert QueueStatusChangedData.model_validate(dumped).status == QueueStatus.PUBLISHED


def test_queue_deleted_data_validates():
    queue_id = uuid4()
    data = QueueDeletedData(queue_id=queue_id)
    assert data.model_dump(mode="json") == {"queue_id": str(queue_id)}


def test_queue_attempt_started_data_validates():
    queue_id = uuid4()
    data = QueueAttemptStartedData(
        queue_id=queue_id,
        attempt_number=1,
        provider="telegram",
    )
    dumped = data.model_dump(mode="json")
    assert dumped == {
        "queue_id": str(queue_id),
        "attempt_number": 1,
        "provider": "telegram",
    }
    assert QueueAttemptStartedData.model_validate(dumped).provider == "telegram"


def test_queue_attempt_succeeded_data_validates():
    queue_id = uuid4()
    data = QueueAttemptSucceededData(
        queue_id=queue_id,
        attempt_number=2,
        provider_message_id=987654321,
    )
    dumped = data.model_dump(mode="json")
    assert dumped["provider_message_id"] == 987654321
    assert QueueAttemptSucceededData.model_validate(dumped).attempt_number == 2


def test_queue_attempt_failed_data_validates():
    queue_id = uuid4()
    data = QueueAttemptFailedData(
        queue_id=queue_id,
        attempt_number=3,
        error_code="dead_letter",
        is_terminal=True,
    )
    dumped = data.model_dump(mode="json")
    assert dumped == {
        "queue_id": str(queue_id),
        "attempt_number": 3,
        "error_code": "dead_letter",
        "is_terminal": True,
    }
    assert QUEUE_STATUS_CHANGED == "queue.status_changed"
    assert QUEUE_DELETED == "queue.deleted"
    assert QUEUE_ATTEMPT_STARTED == "queue.attempt_started"
    assert QUEUE_ATTEMPT_SUCCEEDED == "queue.attempt_succeeded"
    assert QUEUE_ATTEMPT_FAILED == "queue.attempt_failed"
