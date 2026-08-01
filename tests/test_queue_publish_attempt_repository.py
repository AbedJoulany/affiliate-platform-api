"""MVP repository coverage for QueuePublishAttemptRepository (Phase A.1 Task 9)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.models.queue import QueuePublishAttempt
from app.repositories.queue import QueuePublishAttemptRepository
from tests.factories.queue_publishing import (
    VALID_CONTENT_HASH,
    create_attempt,
    create_publishable_queue_item,
)


@pytest.mark.asyncio
async def test_create_attempt_persists_row_with_id(session):
    item = await create_publishable_queue_item(session)
    repo = QueuePublishAttemptRepository(session)
    now = datetime.now(UTC)

    created = await repo.create_attempt(
        QueuePublishAttempt(
            queue_id=item.id,
            attempt_number=1,
            provider="telegram",
            status="started",
            content_hash=VALID_CONTENT_HASH,
            idempotency_expires_at=now + timedelta(hours=24),
            occurred_at=now,
        )
    )

    assert created.id is not None
    assert created.queue_id == item.id
    assert created.status == "started"


@pytest.mark.asyncio
async def test_list_attempts_newest_first(session):
    item = await create_publishable_queue_item(session)
    await create_attempt(session, item.id, attempt_number=1)
    await create_attempt(session, item.id, attempt_number=2)
    await create_attempt(session, item.id, attempt_number=3)
    repo = QueuePublishAttemptRepository(session)

    listed = await repo.list_attempts(item.id)

    assert [a.attempt_number for a in listed] == [3, 2, 1]


@pytest.mark.asyncio
async def test_latest_attempt_returns_highest_or_none(session):
    item = await create_publishable_queue_item(session)
    other = await create_publishable_queue_item(session)
    repo = QueuePublishAttemptRepository(session)

    assert await repo.latest_attempt(item.id) is None

    await create_attempt(session, item.id, attempt_number=1)
    await create_attempt(session, item.id, attempt_number=2)
    latest = await repo.latest_attempt(item.id)

    assert latest is not None
    assert latest.attempt_number == 2
    assert await repo.latest_attempt(other.id) is None


@pytest.mark.asyncio
async def test_active_guard_lookup_matches_unexpired_started_or_succeeded(session):
    item = await create_publishable_queue_item(session)
    repo = QueuePublishAttemptRepository(session)
    now = datetime.now(UTC)
    content_hash = "b" * 64

    started = await create_attempt(
        session,
        item.id,
        attempt_number=1,
        status="started",
        content_hash=content_hash,
        expires_at=now + timedelta(hours=1),
    )
    found_started = await repo.active_guard_lookup(item.id, content_hash, now=now)
    assert found_started is not None
    assert found_started.id == started.id

    await create_attempt(
        session,
        item.id,
        attempt_number=2,
        status="succeeded",
        content_hash=content_hash,
        expires_at=now + timedelta(hours=1),
    )
    found_succeeded = await repo.active_guard_lookup(item.id, content_hash, now=now)
    assert found_succeeded is not None
    assert found_succeeded.status == "succeeded"
    assert found_succeeded.attempt_number == 2


@pytest.mark.asyncio
async def test_active_guard_lookup_ignores_failed_or_expired(session):
    item = await create_publishable_queue_item(session)
    repo = QueuePublishAttemptRepository(session)
    now = datetime.now(UTC)
    content_hash = "c" * 64

    await create_attempt(
        session,
        item.id,
        attempt_number=1,
        status="failed",
        content_hash=content_hash,
        expires_at=now + timedelta(hours=1),
    )
    await create_attempt(
        session,
        item.id,
        attempt_number=2,
        status="started",
        content_hash=content_hash,
        expires_at=now - timedelta(minutes=1),
    )

    assert await repo.active_guard_lookup(item.id, content_hash, now=now) is None
