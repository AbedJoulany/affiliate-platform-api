"""Focused tests for Phase A.2 event emission integration (Task B3)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from app.core.enums import QueueStatus
from app.events.schemas import (
    QUEUE_ATTEMPT_FAILED,
    QUEUE_ATTEMPT_STARTED,
    QUEUE_ATTEMPT_SUCCEEDED,
    QUEUE_DELETED,
    QUEUE_STATUS_CHANGED,
    QueueEventEnvelope,
)
from app.schemas.queue import QueueUpdate
from app.services.exceptions import ConflictError, TelegramPublishError
from app.services.queue import DEAD_LETTER_ERROR_CODE, QueueService, TelegramPublishingService
from tests.factories.queue_publishing import create_attempt, create_publishable_queue_item


class _RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[QueueEventEnvelope] = []

    async def publish(self, event: QueueEventEnvelope) -> int:
        self.events.append(event)
        return 1


def _events_named(recorder: _RecordingPublisher, name: str) -> list[QueueEventEnvelope]:
    return [event for event in recorder.events if event.event == name]


@pytest.mark.asyncio
async def test_status_change_emits_queue_status_changed(session):
    item = await create_publishable_queue_item(session, status=QueueStatus.DRAFT)
    recorder = _RecordingPublisher()
    service = QueueService(session, events=recorder)

    updated = await service.update(
        item.id,
        QueueUpdate(status=QueueStatus.QUEUED),
    )

    changed = _events_named(recorder, QUEUE_STATUS_CHANGED)
    assert len(changed) == 1
    envelope = changed[0]
    assert envelope.queue_id == item.id
    assert envelope.workspace_id is None
    assert UUID(envelope.id)
    assert envelope.data["previous_status"] == QueueStatus.DRAFT.value
    assert envelope.data["status"] == QueueStatus.QUEUED.value
    assert envelope.data["queue_id"] == str(item.id)
    assert updated.status == QueueStatus.QUEUED


@pytest.mark.asyncio
async def test_noop_status_assignment_does_not_emit(session):
    item = await create_publishable_queue_item(session, status=QueueStatus.QUEUED)
    recorder = _RecordingPublisher()
    service = QueueService(session, events=recorder)

    await service.update(item.id, QueueUpdate(status=QueueStatus.QUEUED, title="same status"))

    assert _events_named(recorder, QUEUE_STATUS_CHANGED) == []


@pytest.mark.asyncio
async def test_delete_emits_queue_deleted(session):
    item = await create_publishable_queue_item(session, status=QueueStatus.SCHEDULED)
    item.scheduled_at = datetime.now(UTC) + timedelta(hours=1)
    await session.flush()
    queue_id = item.id
    recorder = _RecordingPublisher()
    service = QueueService(session, events=recorder)

    await service.delete(queue_id)

    deleted = _events_named(recorder, QUEUE_DELETED)
    assert len(deleted) == 1
    envelope = deleted[0]
    assert envelope.queue_id == queue_id
    assert envelope.data == {"queue_id": str(queue_id)}
    assert UUID(envelope.id)


@pytest.mark.asyncio
async def test_attempt_started_and_succeeded_emit_once(
    session,
    mock_telegram_publisher_success,
):
    item = await create_publishable_queue_item(session, content="Emit success path")
    recorder = _RecordingPublisher()
    service = TelegramPublishingService(session, events=recorder)

    response = await service.publish_queue_item(item.id)

    started = _events_named(recorder, QUEUE_ATTEMPT_STARTED)
    succeeded = _events_named(recorder, QUEUE_ATTEMPT_SUCCEEDED)
    changed = _events_named(recorder, QUEUE_STATUS_CHANGED)
    assert len(started) == 1
    assert len(succeeded) == 1
    assert len(changed) == 1
    assert started[0].data["attempt_number"] == 1
    assert started[0].data["provider"] == "telegram"
    assert started[0].data["queue_id"] == str(item.id)
    assert succeeded[0].data["attempt_number"] == 1
    assert succeeded[0].data["provider_message_id"] == response.telegram_message_id
    assert changed[0].data["previous_status"] == QueueStatus.QUEUED.value
    assert changed[0].data["status"] == QueueStatus.PUBLISHED.value
    assert {e.id for e in recorder.events} == {e.id for e in recorder.events}
    assert len({e.id for e in recorder.events}) == 3


@pytest.mark.asyncio
async def test_attempt_failed_emits_terminal_failure(
    session,
    mock_telegram_publisher_failure,
):
    item = await create_publishable_queue_item(session, content="Emit failure path")
    recorder = _RecordingPublisher()
    service = TelegramPublishingService(session, events=recorder)

    with pytest.raises(TelegramPublishError):
        await service.publish_queue_item(
            item.id,
            mark_transport_failure_terminal=True,
        )

    started = _events_named(recorder, QUEUE_ATTEMPT_STARTED)
    failed = _events_named(recorder, QUEUE_ATTEMPT_FAILED)
    assert len(started) == 1
    assert len(failed) == 1
    assert failed[0].data["attempt_number"] == 1
    assert failed[0].data["error_code"] == DEAD_LETTER_ERROR_CODE
    assert failed[0].data["is_terminal"] is True
    assert _events_named(recorder, QUEUE_ATTEMPT_SUCCEEDED) == []
    assert _events_named(recorder, QUEUE_STATUS_CHANGED) == []


@pytest.mark.asyncio
async def test_guard_suppression_without_heal_emits_nothing(
    session,
    mock_telegram_publisher_success,
):
    item = await create_publishable_queue_item(session, content="Idempotent suppress")
    first = _RecordingPublisher()
    await TelegramPublishingService(session, events=first).publish_queue_item(item.id)

    recorder = _RecordingPublisher()
    service = TelegramPublishingService(session, events=recorder)
    with pytest.raises(ConflictError):
        await service.publish_queue_item(item.id)

    assert recorder.events == []


@pytest.mark.asyncio
async def test_status_heal_emits_status_changed_only(
    session,
    mock_telegram_publisher_success,
):
    item = await create_publishable_queue_item(
        session,
        content="Heal drift content",
        status=QueueStatus.SCHEDULED,
    )
    item.scheduled_at = datetime.now(UTC) - timedelta(minutes=1)
    await session.flush()

    service_for_hash = TelegramPublishingService(session)
    snapshot = service_for_hash._build_publish_snapshot(item)
    await create_attempt(
        session,
        item.id,
        attempt_number=1,
        status="succeeded",
        content_hash=snapshot.content_hash,
        provider_chat_id=item.channel.telegram_channel_id,
        provider_message_id=26,
    )

    recorder = _RecordingPublisher()
    service = TelegramPublishingService(session, events=recorder)
    with pytest.raises(ConflictError):
        await service.publish_queue_item(item.id)

    assert _events_named(recorder, QUEUE_ATTEMPT_STARTED) == []
    changed = _events_named(recorder, QUEUE_STATUS_CHANGED)
    assert len(changed) == 1
    assert changed[0].data["previous_status"] == QueueStatus.SCHEDULED.value
    assert changed[0].data["status"] == QueueStatus.PUBLISHED.value
    assert mock_telegram_publisher_success == []


@pytest.mark.asyncio
async def test_event_publish_failure_is_logged_not_silent(session):
    item = await create_publishable_queue_item(session, status=QueueStatus.DRAFT)
    failing = AsyncMock()
    failing.publish = AsyncMock(side_effect=ConnectionError("redis down"))
    service = QueueService(session, events=failing)

    # Domain update must still succeed; enhancement-layer Redis failure is logged.
    updated = await service.update(item.id, QueueUpdate(status=QueueStatus.QUEUED))
    assert updated.status == QueueStatus.QUEUED
    failing.publish.assert_awaited_once()
