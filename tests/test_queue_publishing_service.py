"""MVP service coverage for successful and failed publish persistence."""

import pytest

from app.core.enums import QueueStatus
from app.repositories.queue import QueuePublishAttemptRepository
from app.services.exceptions import TelegramPublishError
from app.services.queue import DEAD_LETTER_ERROR_CODE, TelegramPublishingService
from app.telegram.types import TelegramPublishResult
from tests.factories.queue_publishing import (
    create_publishable_channel,
    create_publishable_queue_item,
)


@pytest.mark.asyncio
async def test_publish_queue_item_happy_path(
    session,
    mock_telegram_publisher_success,
):
    item = await create_publishable_queue_item(session, content="Happy path content")
    chat_id = item.channel.telegram_channel_id
    service = TelegramPublishingService(session)

    response = await service.publish_queue_item(item.id)

    assert response.queue_id == item.id
    assert response.telegram_message_id == 123456789
    assert response.chat_id == chat_id
    assert response.message_type == "text"
    assert response.published_at is not None
    assert len(mock_telegram_publisher_success) == 1

    await session.refresh(item)
    assert item.status == QueueStatus.PUBLISHED
    assert item.published_at is not None
    assert item.telegram_message_id == 123456789

    latest = await QueuePublishAttemptRepository(session).latest_attempt(item.id)
    assert latest is not None
    assert latest.status == "succeeded"
    assert latest.provider_message_id == 123456789
    assert latest.provider_chat_id == chat_id


@pytest.mark.asyncio
async def test_telegram_failure_persists_failed_attempt(
    session,
    mock_telegram_publisher_failure,
):
    item = await create_publishable_queue_item(session, content="Will fail transport")
    original_status = item.status
    service = TelegramPublishingService(session)

    with pytest.raises(TelegramPublishError):
        await service.publish_queue_item(item.id)

    await session.refresh(item)
    assert item.status == original_status
    assert item.status in {
        QueueStatus.DRAFT,
        QueueStatus.QUEUED,
        QueueStatus.SCHEDULED,
        QueueStatus.PUBLISHED,
    }
    assert item.published_at is None

    latest = await QueuePublishAttemptRepository(session).latest_attempt(item.id)
    assert latest is not None
    assert latest.status == "failed"
    assert latest.error_code is not None
    assert latest.error_message is not None
    assert latest.error_code != DEAD_LETTER_ERROR_CODE
    assert len(mock_telegram_publisher_failure) == 1


@pytest.mark.asyncio
async def test_batch_validation_failure_persists_attempt_and_continues(
    session,
    monkeypatch,
):
    inactive = await create_publishable_channel(session, is_active=False)
    failing = await create_publishable_queue_item(
        session,
        channel=inactive,
        content="Inactive channel batch path",
        status=QueueStatus.QUEUED,
    )
    ok_channel = await create_publishable_channel(session)
    succeeding = await create_publishable_queue_item(
        session,
        channel=ok_channel,
        content="Second item after failure",
        status=QueueStatus.QUEUED,
    )

    async def fake_publish(
        self,
        chat_id,
        text,
        *,
        image_url=None,
        button=None,
        parse_mode=None,
    ):
        return TelegramPublishResult(
            chat_id=str(chat_id),
            message_id=555,
            message_type="text",
        )

    monkeypatch.setattr(
        "app.telegram.publisher.TelegramPublisher.publish",
        fake_publish,
    )
    service = TelegramPublishingService(session)

    results = await service._publish_items([failing, succeeding])

    failed = await QueuePublishAttemptRepository(session).latest_attempt(failing.id)
    assert failed is not None
    assert failed.status == "failed"
    assert failed.error_code == DEAD_LETTER_ERROR_CODE

    await session.refresh(failing)
    assert failing.status == QueueStatus.QUEUED

    assert len(results) == 1
    assert results[0].queue_id == succeeding.id
    ok_latest = await QueuePublishAttemptRepository(session).latest_attempt(succeeding.id)
    assert ok_latest is not None
    assert ok_latest.status == "succeeded"


@pytest.mark.asyncio
async def test_batch_telegram_failure_does_not_block_sibling(
    session,
    monkeypatch,
):
    """One TelegramPublishError must not abort the rest of a due/queued batch."""
    from datetime import UTC, datetime, timedelta

    failing = await create_publishable_queue_item(
        session,
        content="Bad caption sibling",
        status=QueueStatus.SCHEDULED,
    )
    failing.scheduled_at = datetime.now(UTC) - timedelta(minutes=5)
    succeeding = await create_publishable_queue_item(
        session,
        content="Healthy scheduled sibling",
        status=QueueStatus.SCHEDULED,
    )
    succeeding.scheduled_at = datetime.now(UTC) - timedelta(minutes=1)
    await session.flush()

    async def fake_publish(
        self,
        chat_id,
        text,
        *,
        image_url=None,
        button=None,
        parse_mode=None,
    ):
        if text.startswith("Bad caption"):
            raise TelegramPublishError(
                "Bad Request: message caption is too long",
                http_status=400,
                telegram_error_code=400,
            )
        return TelegramPublishResult(
            chat_id=str(chat_id),
            message_id=777,
            message_type="text",
        )

    monkeypatch.setattr(
        "app.telegram.publisher.TelegramPublisher.publish",
        fake_publish,
    )
    service = TelegramPublishingService(session)

    results = await service.publish_due_scheduled(limit=50)

    assert any(r.queue_id == succeeding.id for r in results)
    await session.refresh(succeeding)
    assert succeeding.status == QueueStatus.PUBLISHED

    failed = await QueuePublishAttemptRepository(session).latest_attempt(failing.id)
    assert failed is not None
    assert failed.status == "failed"
    assert failed.error_code == DEAD_LETTER_ERROR_CODE
    await session.refresh(failing)
    assert failing.status == QueueStatus.SCHEDULED


@pytest.mark.asyncio
async def test_succeeded_attempt_heals_scheduled_status_drift(
    session,
    mock_telegram_publisher_success,
):
    """Guard suppress after a prior Telegram success should mark the item published."""
    from datetime import UTC, datetime, timedelta

    from app.services.exceptions import ConflictError
    from tests.factories.queue_publishing import create_attempt

    item = await create_publishable_queue_item(
        session,
        content="Already sent to telegram",
        status=QueueStatus.SCHEDULED,
    )
    item.scheduled_at = datetime.now(UTC) - timedelta(minutes=1)
    await session.flush()

    service = TelegramPublishingService(session)
    snapshot = service._build_publish_snapshot(item)
    await create_attempt(
        session,
        item.id,
        attempt_number=1,
        status="succeeded",
        content_hash=snapshot.content_hash,
        provider_chat_id=item.channel.telegram_channel_id,
        provider_message_id=26,
    )

    with pytest.raises(ConflictError):
        await service.publish_queue_item(item.id)

    assert mock_telegram_publisher_success == []
    await session.refresh(item)
    assert item.status == QueueStatus.PUBLISHED
    assert item.telegram_message_id == 26
