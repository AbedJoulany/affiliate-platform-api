"""Redis Pub/Sub consumer for Phase A.2 queue events.

Subscribes to the shared ``queue-events`` channel, validates each message as a
``QueueEventEnvelope``, and forwards valid envelopes to an ``EventBroadcaster``.
No SSE/HTTP knowledge lives here.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Protocol

from pydantic import ValidationError

from app.events.broadcaster import EventBroadcaster
from app.events.publisher import DEFAULT_EVENT_STREAM_CHANNEL
from app.events.schemas import QueueEventEnvelope

logger = logging.getLogger(__name__)


class SupportsRedisPubSub(Protocol):
    """Minimal async Redis surface: factory for a Pub/Sub object."""

    def pubsub(self) -> Any: ...


class EventConsumer:
    """Subscribe to Redis Pub/Sub and fan events into an ``EventBroadcaster``."""

    def __init__(
        self,
        redis_client: SupportsRedisPubSub,
        broadcaster: EventBroadcaster,
        *,
        channel_name: str = DEFAULT_EVENT_STREAM_CHANNEL,
        reconnect_delay_seconds: float = 1.0,
        poll_timeout_seconds: float = 1.0,
    ) -> None:
        self._redis = redis_client
        self._broadcaster = broadcaster
        self._channel_name = channel_name
        self._reconnect_delay_seconds = reconnect_delay_seconds
        self._poll_timeout_seconds = poll_timeout_seconds
        self._task: asyncio.Task[None] | None = None
        self._pubsub: Any | None = None
        self._stopped = True

    @property
    def broadcaster(self) -> EventBroadcaster:
        """Broadcaster this consumer publishes validated envelopes into."""
        return self._broadcaster

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        """Begin consuming in a background task. Idempotent while already running."""
        if self.is_running:
            return
        self._stopped = False
        self._task = asyncio.create_task(self._run_loop(), name="queue-event-consumer")

    async def stop(self) -> None:
        """Stop consuming, cancel the loop, and close Pub/Sub resources."""
        self._stopped = True
        task = self._task
        self._task = None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        await self._close_pubsub()

    async def _run_loop(self) -> None:
        while not self._stopped:
            try:
                await self._consume_session()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "EventConsumer Redis session failed on channel %s; reconnecting",
                    self._channel_name,
                )
                await self._close_pubsub()
                if self._stopped:
                    break
                await asyncio.sleep(self._reconnect_delay_seconds)

    async def _consume_session(self) -> None:
        pubsub = self._redis.pubsub()
        self._pubsub = pubsub
        await pubsub.subscribe(self._channel_name)
        try:
            while not self._stopped:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=False,
                    timeout=self._poll_timeout_seconds,
                )
                if message is None:
                    continue
                await self._handle_raw_message(message)
        finally:
            await self._close_pubsub()

    async def _handle_raw_message(self, message: dict[str, Any]) -> None:
        if message.get("type") != "message":
            return

        raw = message.get("data")
        if raw is None:
            return
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        if not isinstance(raw, str):
            logger.error(
                "Invalid event payload received, skipping: data type %s",
                type(raw).__name__,
            )
            return

        try:
            envelope = QueueEventEnvelope.model_validate_json(raw)
        except (ValidationError, ValueError):
            logger.exception("Invalid event payload received, skipping")
            return

        await self._broadcaster.publish(envelope)

    async def _close_pubsub(self) -> None:
        pubsub = self._pubsub
        self._pubsub = None
        if pubsub is None:
            return
        try:
            await pubsub.unsubscribe(self._channel_name)
        except Exception:
            logger.exception("EventConsumer unsubscribe failed for %s", self._channel_name)
        try:
            aclose = getattr(pubsub, "aclose", None)
            if aclose is not None:
                await aclose()
            else:
                close = getattr(pubsub, "close", None)
                if close is not None:
                    result = close()
                    if asyncio.iscoroutine(result):
                        await result
        except Exception:
            logger.exception("EventConsumer pubsub close failed for %s", self._channel_name)
