"""Unit tests for Phase A.2 EventPublisher (Task B2)."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from app.events.publisher import (
    DEFAULT_EVENT_STREAM_CHANNEL,
    EventPublisher,
    NullEventPublisher,
)
from app.events.schemas import QUEUE_ATTEMPT_FAILED, QueueEventEnvelope

QUEUE_ID = UUID("6f9c2e34-2b1a-4b2e-9f0a-1234567890ab")
OCCURRED_AT = datetime(2026, 8, 7, 9, 40, 12, 483000, tzinfo=UTC)


def _sample_envelope() -> QueueEventEnvelope:
    return QueueEventEnvelope(
        event=QUEUE_ATTEMPT_FAILED,
        version=1,
        id="01J9Z8H5F9T4S1R7D8P2K3M4N5",
        occurred_at=OCCURRED_AT,
        workspace_id=None,
        queue_id=QUEUE_ID,
        data={
            "queue_id": str(QUEUE_ID),
            "attempt_number": 3,
            "error_code": "dead_letter",
            "is_terminal": True,
        },
    )


@pytest.mark.asyncio
async def test_event_publisher_publishes_to_configured_channel():
    fake_redis = AsyncMock()
    fake_redis.publish = AsyncMock(return_value=1)
    publisher = EventPublisher(fake_redis, channel_name=DEFAULT_EVENT_STREAM_CHANNEL)

    await publisher.publish(_sample_envelope())

    fake_redis.publish.assert_awaited_once()
    channel, payload = fake_redis.publish.await_args.args
    assert channel == "queue-events"
    assert isinstance(payload, str)
    json.loads(payload)


@pytest.mark.asyncio
async def test_event_publisher_serialized_payload_matches_envelope():
    fake_redis = AsyncMock()
    fake_redis.publish = AsyncMock(return_value=0)
    publisher = EventPublisher(fake_redis)
    event = _sample_envelope()

    await publisher.publish(event)

    payload = fake_redis.publish.await_args.args[1]
    decoded = json.loads(payload)
    expected = json.loads(event.model_dump_json())
    assert decoded == expected
    assert decoded["event"] == QUEUE_ATTEMPT_FAILED
    assert decoded["version"] == 1
    assert decoded["id"] == "01J9Z8H5F9T4S1R7D8P2K3M4N5"
    assert decoded["workspace_id"] is None
    assert decoded["queue_id"] == str(QUEUE_ID)
    assert decoded["data"] == {
        "queue_id": str(QUEUE_ID),
        "attempt_number": 3,
        "error_code": "dead_letter",
        "is_terminal": True,
    }
    assert "occurred_at" in decoded


@pytest.mark.asyncio
async def test_null_event_publisher_does_nothing():
    publisher = NullEventPublisher()
    await publisher.publish(_sample_envelope())


@pytest.mark.asyncio
async def test_event_publisher_propagates_redis_exceptions():
    fake_redis = AsyncMock()
    fake_redis.publish = AsyncMock(side_effect=ConnectionError("redis unavailable"))
    publisher = EventPublisher(fake_redis)

    with pytest.raises(ConnectionError, match="redis unavailable"):
        await publisher.publish(_sample_envelope())
