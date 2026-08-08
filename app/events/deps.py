"""Process-local dependency hooks for Phase A.2 event transport.

SSE and ``EventConsumer`` (app lifespan) both resolve the process-wide
``EventBroadcaster`` through ``get_event_broadcaster()``.

``get_event_publisher`` wraps the lifespan Redis client (``app.state.event_redis``)
in an ``EventPublisher`` for API request handlers. Celery tasks build a publisher
with ``create_event_publisher`` around a short-lived Redis client.
"""

from __future__ import annotations

from fastapi import Request

from app.events.broadcaster import EventBroadcaster
from app.events.publisher import EventPublisher, NullEventPublisher, SupportsRedisPublish

_broadcaster: EventBroadcaster | None = None


def get_event_broadcaster() -> EventBroadcaster:
    """Return the process-wide broadcaster, creating it on first use."""
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = EventBroadcaster()
    return _broadcaster


def create_event_publisher(
    redis_client: SupportsRedisPublish,
    *,
    channel_name: str | None = None,
) -> EventPublisher:
    """Build a Redis-backed publisher. Used by API deps and Celery workers."""
    if channel_name is None:
        return EventPublisher(redis_client)
    return EventPublisher(redis_client, channel_name=channel_name)


def get_event_publisher(request: Request) -> EventPublisher | NullEventPublisher:
    """Return production ``EventPublisher`` when lifespan Redis is available.

    Falls back to ``NullEventPublisher`` when ``app.state.event_redis`` is unset
    (e.g. unit tests that never enter FastAPI lifespan). Production uvicorn
    always starts lifespan and sets the client.
    """
    redis_client = getattr(request.app.state, "event_redis", None)
    if redis_client is None:
        return NullEventPublisher()
    return create_event_publisher(redis_client)
