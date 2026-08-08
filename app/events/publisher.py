"""Minimal Redis Pub/Sub transport for Phase A.2 queue events.

Accepts a validated ``QueueEventEnvelope``, serializes it to JSON, and
``PUBLISH``es to exactly one channel. No business-event construction,
persistence, retry, or SSE logic lives here.
"""

from typing import Protocol

from app.events.schemas import QueueEventEnvelope

# Local default until B7 adds ``event_stream_channel_name`` to Settings.
DEFAULT_EVENT_STREAM_CHANNEL = "queue-events"


class SupportsRedisPublish(Protocol):
    """Minimal async Redis surface required by ``EventPublisher``."""

    async def publish(self, channel: str, message: bytes | str) -> int: ...


class EventPublisher:
    """Publish validated event envelopes to a single Redis Pub/Sub channel."""

    def __init__(
        self,
        redis_client: SupportsRedisPublish,
        *,
        channel_name: str = DEFAULT_EVENT_STREAM_CHANNEL,
    ) -> None:
        self._redis = redis_client
        self._channel_name = channel_name

    async def publish(self, event: QueueEventEnvelope) -> int:
        """Serialize ``event`` and PUBLISH it to the configured channel.

        Returns the Redis ``PUBLISH`` result (subscriber count). Exceptions from
        Redis propagate unchanged — callers decide how to handle delivery failure.
        """
        payload = event.model_dump_json()
        return await self._redis.publish(self._channel_name, payload)


class NullEventPublisher:
    """No-op publisher for tests and environments without live event delivery."""

    async def publish(self, event: QueueEventEnvelope) -> None:
        return None
