"""Unit tests for Phase A.2 EventBroadcaster (Task B4)."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.events.broadcaster import EventBroadcaster
from app.events.schemas import QUEUE_ATTEMPT_FAILED, QueueEventEnvelope

QUEUE_ID = UUID("6f9c2e34-2b1a-4b2e-9f0a-1234567890ab")


def _sample_envelope() -> QueueEventEnvelope:
    return QueueEventEnvelope(
        event=QUEUE_ATTEMPT_FAILED,
        version=1,
        id="01J9Z8H5F9T4S1R7D8P2K3M4N5",
        occurred_at=datetime(2026, 8, 7, 9, 40, 12, 483000, tzinfo=UTC),
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
async def test_subscriber_receives_events():
    broadcaster = EventBroadcaster()
    received: list[QueueEventEnvelope] = []

    async def on_event(event: QueueEventEnvelope) -> None:
        received.append(event)

    broadcaster.subscribe(on_event)
    envelope = _sample_envelope()
    await broadcaster.publish(envelope)

    assert received == [envelope]


@pytest.mark.asyncio
async def test_subscriber_failure_is_isolated(caplog):
    broadcaster = EventBroadcaster()
    received: list[QueueEventEnvelope] = []

    async def ok(event: QueueEventEnvelope) -> None:
        received.append(event)

    async def boom(_event: QueueEventEnvelope) -> None:
        raise RuntimeError("subscriber boom")

    broadcaster.subscribe(ok)
    broadcaster.subscribe(boom)
    # Registration order: ok then boom — also test boom-then-ok order.
    broadcaster2 = EventBroadcaster()
    received2: list[QueueEventEnvelope] = []

    async def boom2(_event: QueueEventEnvelope) -> None:
        raise RuntimeError("first fails")

    async def ok2(event: QueueEventEnvelope) -> None:
        received2.append(event)

    broadcaster2.subscribe(boom2)
    broadcaster2.subscribe(ok2)

    envelope = _sample_envelope()
    with caplog.at_level("ERROR"):
        await broadcaster.publish(envelope)
        await broadcaster2.publish(envelope)

    assert received == [envelope]
    assert received2 == [envelope]
    assert "subscriber boom" in caplog.text or "first fails" in caplog.text


@pytest.mark.asyncio
async def test_unsubscribe_stops_delivery():
    broadcaster = EventBroadcaster()
    received: list[QueueEventEnvelope] = []

    async def on_event(event: QueueEventEnvelope) -> None:
        received.append(event)

    subscriber_id = broadcaster.subscribe(on_event)
    broadcaster.unsubscribe(subscriber_id)
    await broadcaster.publish(_sample_envelope())

    assert received == []
