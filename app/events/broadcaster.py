"""In-process fan-out for validated queue event envelopes.

Transports (SSE, etc.) register callbacks here. This module has no Redis or
HTTP knowledge — it only delivers already-validated ``QueueEventEnvelope``
instances to registered async subscribers.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from uuid import uuid4

from app.events.schemas import QueueEventEnvelope

logger = logging.getLogger(__name__)

EventSubscriber = Callable[[QueueEventEnvelope], Awaitable[None]]


class EventBroadcaster:
    """Register async callbacks and deliver events sequentially."""

    def __init__(self) -> None:
        self._subscribers: dict[str, EventSubscriber] = {}

    def subscribe(self, callback: EventSubscriber) -> str:
        """Register ``callback`` and return a subscriber id for later removal."""
        subscriber_id = str(uuid4())
        self._subscribers[subscriber_id] = callback
        return subscriber_id

    def unsubscribe(self, subscriber_id: str) -> None:
        """Remove a previously registered subscriber. Unknown ids are ignored."""
        self._subscribers.pop(subscriber_id, None)

    async def publish(self, event: QueueEventEnvelope) -> None:
        """Deliver ``event`` to every subscriber in registration order.

        One subscriber failure is logged and isolated; later subscribers still
        receive the same event. Delivery is sequential to preserve order.
        """
        for subscriber_id, callback in list(self._subscribers.items()):
            try:
                await callback(event)
            except Exception:
                logger.exception(
                    "EventBroadcaster subscriber %s failed for event %s queue_id=%s",
                    subscriber_id,
                    event.event,
                    event.queue_id,
                )
