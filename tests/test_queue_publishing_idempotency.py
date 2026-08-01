"""MVP idempotency-guard coverage for Telegram publish."""

import pytest

from app.core.enums import QueueStatus
from app.repositories.queue import QueuePublishAttemptRepository
from app.services.exceptions import ConflictError
from app.services.queue import TelegramPublishingService
from tests.factories.queue_publishing import create_publishable_queue_item


@pytest.mark.asyncio
async def test_second_publish_same_content_conflicts_without_new_attempt(
    session,
    mock_telegram_publisher_success,
):
    item = await create_publishable_queue_item(session, content="Idempotent content")
    service = TelegramPublishingService(session)

    await service.publish_queue_item(item.id)
    assert len(mock_telegram_publisher_success) == 1

    with pytest.raises(ConflictError):
        await service.publish_queue_item(item.id)

    assert len(mock_telegram_publisher_success) == 1
    attempts = await QueuePublishAttemptRepository(session).list_attempts(item.id)
    assert len(attempts) == 1
    assert attempts[0].status == "succeeded"


@pytest.mark.asyncio
async def test_content_edit_allows_fresh_publish_attempt(
    session,
    mock_telegram_publisher_success,
):
    item = await create_publishable_queue_item(session, content="Original content")
    service = TelegramPublishingService(session)

    await service.publish_queue_item(item.id)
    assert len(mock_telegram_publisher_success) == 1

    # Reset to a publishable status and change content so the guard sees a new hash.
    item.content = "Edited content for republish"
    item.status = QueueStatus.QUEUED
    item.published_at = None
    item.telegram_message_id = None
    await session.flush()

    response = await service.publish_queue_item(item.id)

    assert response.telegram_message_id == 123456789
    assert len(mock_telegram_publisher_success) == 2
    attempts = await QueuePublishAttemptRepository(session).list_attempts(item.id)
    assert len(attempts) == 2
    assert {a.status for a in attempts} == {"succeeded"}
