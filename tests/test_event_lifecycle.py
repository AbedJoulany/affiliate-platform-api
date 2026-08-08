"""Tests for Phase A.2 EventConsumer FastAPI lifespan wiring (Task B6)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.events.consumer import EventConsumer
from app.events.deps import get_event_broadcaster
from app.main import app, lifespan


class _FakePubSub:
    async def subscribe(self, *_args, **_kwargs) -> None:
        return None

    async def get_message(self, **_kwargs):
        await asyncio.sleep(0.05)
        return None

    async def unsubscribe(self, *_args, **_kwargs) -> None:
        return None

    async def aclose(self) -> None:
        return None


class _FakeRedis:
    def __init__(self) -> None:
        self.closed = False

    def pubsub(self) -> _FakePubSub:
        return _FakePubSub()

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_lifespan_starts_consumer_with_shared_broadcaster():
    fake_redis = _FakeRedis()

    with patch("app.main.redis.from_url", return_value=fake_redis):
        async with lifespan(app):
            consumer = app.state.event_consumer
            assert isinstance(consumer, EventConsumer)
            assert consumer.is_running is True
            assert consumer.broadcaster is get_event_broadcaster()
            assert app.state.event_redis is fake_redis

        assert app.state.event_consumer is None
        assert app.state.event_redis is None
        assert fake_redis.closed is True
        assert consumer.is_running is False


@pytest.mark.asyncio
async def test_lifespan_calls_start_and_stop():
    fake_redis = MagicMock()
    fake_redis.aclose = AsyncMock()
    start = AsyncMock()
    stop = AsyncMock()

    with (
        patch("app.main.redis.from_url", return_value=fake_redis),
        patch.object(EventConsumer, "start", start),
        patch.object(EventConsumer, "stop", stop),
    ):
        async with lifespan(app):
            start.assert_awaited_once()
            stop.assert_not_awaited()
            consumer = app.state.event_consumer
            assert isinstance(consumer, EventConsumer)
            assert consumer.broadcaster is get_event_broadcaster()

        stop.assert_awaited_once()

    fake_redis.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_lifespan_closes_redis_after_consumer_stop():
    fake_redis = MagicMock()
    fake_redis.aclose = AsyncMock()
    call_order: list[str] = []

    async def stop_side_effect(self) -> None:
        call_order.append("stop")

    async def aclose_side_effect() -> None:
        call_order.append("aclose")

    fake_redis.aclose = AsyncMock(side_effect=aclose_side_effect)

    with (
        patch("app.main.redis.from_url", return_value=fake_redis),
        patch.object(EventConsumer, "start", new_callable=AsyncMock),
        patch.object(EventConsumer, "stop", stop_side_effect),
    ):
        async with lifespan(app):
            pass

    assert call_order == ["stop", "aclose"]
