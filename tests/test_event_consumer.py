"""Unit tests for Phase A.2 EventConsumer (Task B4)."""

import asyncio
import json
from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.events.broadcaster import EventBroadcaster
from app.events.consumer import EventConsumer
from app.events.publisher import DEFAULT_EVENT_STREAM_CHANNEL
from app.events.schemas import QUEUE_STATUS_CHANGED, QueueEventEnvelope

QUEUE_ID = UUID("6f9c2e34-2b1a-4b2e-9f0a-1234567890ab")


def _sample_envelope() -> QueueEventEnvelope:
    return QueueEventEnvelope(
        event=QUEUE_STATUS_CHANGED,
        version=1,
        id="01J9Z8H5F9T4S1R7D8P2K3M4N5",
        occurred_at=datetime(2026, 8, 7, 9, 40, 12, 483000, tzinfo=UTC),
        workspace_id=None,
        queue_id=QUEUE_ID,
        data={
            "queue_id": str(QUEUE_ID),
            "status": "published",
            "previous_status": "queued",
            "scheduled_at": None,
            "published_at": "2026-08-07T09:40:12.483000Z",
        },
    )


class FakePubSub:
    def __init__(self) -> None:
        self._messages: asyncio.Queue[dict | None] = asyncio.Queue()
        self.subscribed_channels: list[str] = []
        self.unsubscribed = False
        self.closed = False

    async def subscribe(self, *channels: str) -> None:
        self.subscribed_channels.extend(channels)

    async def unsubscribe(self, *channels: str) -> None:
        self.unsubscribed = True

    async def get_message(
        self,
        ignore_subscribe_messages: bool = False,
        timeout: float | None = 0.0,
    ) -> dict | None:
        try:
            return await asyncio.wait_for(self._messages.get(), timeout=timeout or 0.05)
        except TimeoutError:
            return None

    async def aclose(self) -> None:
        self.closed = True

    def push(self, message: dict) -> None:
        self._messages.put_nowait(message)


class FakeRedis:
    def __init__(self, pubsub: FakePubSub) -> None:
        self._pubsub = pubsub
        self.pubsub_calls = 0

    def pubsub(self) -> FakePubSub:
        self.pubsub_calls += 1
        return self._pubsub


async def _wait_until(predicate, *, timeout: float = 1.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition not met before timeout")


@pytest.mark.asyncio
async def test_valid_event_is_forwarded_to_broadcaster():
    pubsub = FakePubSub()
    redis = FakeRedis(pubsub)
    broadcaster = EventBroadcaster()
    received: list[QueueEventEnvelope] = []

    async def on_event(event: QueueEventEnvelope) -> None:
        received.append(event)

    broadcaster.subscribe(on_event)
    consumer = EventConsumer(
        redis,
        broadcaster,
        reconnect_delay_seconds=0.05,
        poll_timeout_seconds=0.05,
    )
    envelope = _sample_envelope()

    await consumer.start()
    await _wait_until(lambda: DEFAULT_EVENT_STREAM_CHANNEL in pubsub.subscribed_channels)
    pubsub.push({"type": "message", "data": envelope.model_dump_json()})
    await _wait_until(lambda: len(received) == 1)
    await consumer.stop()

    assert received[0].event == QUEUE_STATUS_CHANGED
    assert received[0].queue_id == QUEUE_ID
    assert pubsub.closed is True


@pytest.mark.asyncio
async def test_invalid_json_is_skipped_and_consumer_continues(caplog):
    pubsub = FakePubSub()
    redis = FakeRedis(pubsub)
    broadcaster = EventBroadcaster()
    received: list[QueueEventEnvelope] = []

    async def on_event(event: QueueEventEnvelope) -> None:
        received.append(event)

    broadcaster.subscribe(on_event)
    consumer = EventConsumer(
        redis,
        broadcaster,
        reconnect_delay_seconds=0.05,
        poll_timeout_seconds=0.05,
    )
    envelope = _sample_envelope()

    await consumer.start()
    await _wait_until(lambda: pubsub.subscribed_channels)
    with caplog.at_level("ERROR"):
        pubsub.push({"type": "message", "data": "not-json{"})
        pubsub.push({"type": "message", "data": envelope.model_dump_json()})
        await _wait_until(lambda: len(received) == 1)
    await consumer.stop()

    assert len(received) == 1
    assert "Invalid event payload received, skipping" in caplog.text


@pytest.mark.asyncio
async def test_invalid_schema_is_skipped_and_consumer_continues(caplog):
    pubsub = FakePubSub()
    redis = FakeRedis(pubsub)
    broadcaster = EventBroadcaster()
    received: list[QueueEventEnvelope] = []

    async def on_event(event: QueueEventEnvelope) -> None:
        received.append(event)

    broadcaster.subscribe(on_event)
    consumer = EventConsumer(
        redis,
        broadcaster,
        reconnect_delay_seconds=0.05,
        poll_timeout_seconds=0.05,
    )
    envelope = _sample_envelope()

    await consumer.start()
    await _wait_until(lambda: pubsub.subscribed_channels)
    with caplog.at_level("ERROR"):
        pubsub.push({"type": "message", "data": json.dumps({"event": "wrong"})})
        pubsub.push({"type": "message", "data": envelope.model_dump_json()})
        await _wait_until(lambda: len(received) == 1)
    await consumer.stop()

    assert len(received) == 1
    assert "Invalid event payload received, skipping" in caplog.text


@pytest.mark.asyncio
async def test_non_message_pubsub_types_are_ignored():
    pubsub = FakePubSub()
    redis = FakeRedis(pubsub)
    broadcaster = EventBroadcaster()
    received: list[QueueEventEnvelope] = []

    async def on_event(event: QueueEventEnvelope) -> None:
        received.append(event)

    broadcaster.subscribe(on_event)
    consumer = EventConsumer(
        redis,
        broadcaster,
        reconnect_delay_seconds=0.05,
        poll_timeout_seconds=0.05,
    )
    envelope = _sample_envelope()

    await consumer.start()
    await _wait_until(lambda: pubsub.subscribed_channels)
    pubsub.push({"type": "subscribe", "data": 1, "channel": DEFAULT_EVENT_STREAM_CHANNEL})
    pubsub.push({"type": "unsubscribe", "data": 0, "channel": DEFAULT_EVENT_STREAM_CHANNEL})
    pubsub.push({"type": "message", "data": envelope.model_dump_json()})
    await _wait_until(lambda: len(received) == 1)
    await consumer.stop()

    assert len(received) == 1


@pytest.mark.asyncio
async def test_stop_closes_pubsub_resources():
    pubsub = FakePubSub()
    redis = FakeRedis(pubsub)
    consumer = EventConsumer(
        redis,
        EventBroadcaster(),
        reconnect_delay_seconds=0.05,
        poll_timeout_seconds=0.05,
    )

    await consumer.start()
    await _wait_until(lambda: pubsub.subscribed_channels)
    assert redis.pubsub_calls == 1
    await consumer.stop()

    assert consumer.is_running is False
    assert pubsub.unsubscribed is True
    assert pubsub.closed is True