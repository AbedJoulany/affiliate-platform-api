"""Tests for Phase A.2 production EventPublisher wiring (Task B7)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.deps import get_queue_service
from app.events.deps import create_event_publisher, get_event_publisher
from app.events.publisher import EventPublisher, NullEventPublisher
from app.services.queue import QueueService, TelegramPublishingService
from app.worker.tasks import publishing as publishing_tasks


def test_create_event_publisher_returns_event_publisher():
    redis_client = MagicMock()
    publisher = create_event_publisher(redis_client)
    assert isinstance(publisher, EventPublisher)
    assert not isinstance(publisher, NullEventPublisher)


def test_get_event_publisher_uses_lifespan_redis():
    redis_client = MagicMock()
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(event_redis=redis_client)))
    publisher = get_event_publisher(request)
    assert isinstance(publisher, EventPublisher)


def test_get_event_publisher_falls_back_to_null_without_lifespan_redis():
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    publisher = get_event_publisher(request)
    assert isinstance(publisher, NullEventPublisher)


def test_get_queue_service_injects_publisher():
    db = MagicMock()
    events = create_event_publisher(MagicMock())
    service = get_queue_service(db, events)
    assert isinstance(service, QueueService)
    assert service.events is events
    assert isinstance(service.publishing_service, TelegramPublishingService)
    assert service.publishing_service.events is events


def test_queue_and_telegram_services_keep_null_default_for_tests():
    db = MagicMock()
    queue_service = QueueService(db)
    telegram_service = TelegramPublishingService(db)
    assert isinstance(queue_service.events, NullEventPublisher)
    assert isinstance(telegram_service.events, NullEventPublisher)


@pytest.mark.asyncio
async def test_celery_process_queue_wires_event_publisher():
    fake_redis = MagicMock()
    fake_redis.aclose = AsyncMock()
    captured: dict[str, object] = {}

    class FakeTelegramService:
        def __init__(self, session, events=None):
            captured["events"] = events

        async def publish_due_scheduled(self, **_kwargs):
            return []

        async def publish_queued_items(self, **_kwargs):
            return []

    session = MagicMock()
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=None)
    session_maker = MagicMock(return_value=session_cm)
    session.commit = AsyncMock()

    with (
        patch.object(publishing_tasks, "get_async_session_maker", return_value=session_maker),
        patch.object(publishing_tasks.redis, "from_url", return_value=fake_redis),
        patch.object(publishing_tasks, "TelegramPublishingService", FakeTelegramService),
    ):
        result = await publishing_tasks._process_publish_queue(batch_size=1)

    assert isinstance(captured["events"], EventPublisher)
    fake_redis.aclose.assert_awaited_once()
    assert result["scheduled_published"] == 0
    assert result["queued_published"] == 0


@pytest.mark.asyncio
async def test_celery_single_publish_wires_event_publisher():
    fake_redis = MagicMock()
    fake_redis.aclose = AsyncMock()
    captured: dict[str, object] = {}
    queue_id = MagicMock()

    class FakeResult:
        def model_dump(self, mode="python"):
            return {"queue_id": "x"}

    class FakeTelegramService:
        def __init__(self, session, events=None):
            captured["events"] = events

        async def publish_queue_item(self, *_args, **_kwargs):
            return FakeResult()

    session = MagicMock()
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=None)
    session_maker = MagicMock(return_value=session_cm)
    session.commit = AsyncMock()

    with (
        patch.object(publishing_tasks, "get_async_session_maker", return_value=session_maker),
        patch.object(publishing_tasks.redis, "from_url", return_value=fake_redis),
        patch.object(publishing_tasks, "TelegramPublishingService", FakeTelegramService),
    ):
        result = await publishing_tasks._publish_single_queue_item(queue_id)

    assert isinstance(captured["events"], EventPublisher)
    fake_redis.aclose.assert_awaited_once()
    assert result == {"queue_id": "x"}
