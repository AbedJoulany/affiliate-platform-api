"""Regression coverage for queue item delete with publish attempts."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.core.enums import QueueStatus
from app.models.queue import QueueItem, QueuePublishAttempt
from app.models.workspace import Workspace
from app.services.queue import QueueService
from tests.factories.queue_publishing import create_attempt, create_publishable_queue_item


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [QueueStatus.DRAFT, QueueStatus.QUEUED, QueueStatus.SCHEDULED],
)
async def test_delete_queue_item_with_attempts(session, status):
    item = await create_publishable_queue_item(
        session,
        content=f"Delete me ({status.value})",
        status=status,
    )
    if status == QueueStatus.SCHEDULED:
        item.scheduled_at = datetime.now(UTC) + timedelta(hours=1)
        await session.flush()

    await create_attempt(session, item.id, attempt_number=1, status="failed")
    await create_attempt(session, item.id, attempt_number=2, status="started")
    workspace = Workspace(name="Delete workspace")
    session.add(workspace)
    await session.flush()
    item.workspace_id = workspace.id
    await session.flush()
    queue_id = item.id

    await QueueService(session).delete(queue_id, workspace.id)
    await session.commit()

    assert await session.get(QueueItem, queue_id) is None
    remaining = await session.scalar(
        select(func.count())
        .select_from(QueuePublishAttempt)
        .where(QueuePublishAttempt.queue_id == queue_id)
    )
    assert remaining == 0
