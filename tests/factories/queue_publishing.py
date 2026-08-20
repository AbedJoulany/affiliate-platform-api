"""Factories for Phase A.1 queue publish-attempt MVP tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import BotPermissionStatus, QueueStatus
from app.models.channel import TelegramChannel
from app.models.queue import QueueItem, QueuePublishAttempt
from app.models.workspace import Workspace

VALID_CONTENT_HASH = "a" * 64


async def _ensure_workspace_id(
    session: AsyncSession,
    workspace_id: UUID | None,
) -> UUID:
    if workspace_id is not None:
        return workspace_id
    workspace = Workspace(name=f"Publish test workspace {uuid4().hex[:8]}")
    session.add(workspace)
    await session.flush()
    return workspace.id


async def create_publishable_channel(
    session: AsyncSession,
    *,
    telegram_channel_id: str | None = None,
    is_active: bool = True,
    bot_permission_status: BotPermissionStatus = BotPermissionStatus.GRANTED,
    can_post_messages: bool = True,
    workspace_id: UUID | None = None,
) -> TelegramChannel:
    workspace_id = await _ensure_workspace_id(session, workspace_id)
    channel = TelegramChannel(
        telegram_channel_id=telegram_channel_id or f"@ch-{uuid4().hex[:10]}",
        title="Publish Test Channel",
        username=f"ch_{uuid4().hex[:8]}",
        bot_permission_status=bot_permission_status,
        can_post_messages=can_post_messages,
        can_edit_messages=True,
        can_delete_messages=True,
        is_active=is_active,
        workspace_id=workspace_id,
    )
    session.add(channel)
    await session.flush()
    await session.refresh(channel)
    return channel


async def create_publishable_queue_item(
    session: AsyncSession,
    *,
    channel: TelegramChannel | None = None,
    content: str = "Publish me",
    status: QueueStatus = QueueStatus.QUEUED,
    title: str | None = "Publish test item",
    workspace_id: UUID | None = None,
) -> QueueItem:
    if workspace_id is None and channel is not None:
        workspace_id = channel.workspace_id
    workspace_id = await _ensure_workspace_id(session, workspace_id)
    if channel is None:
        channel = await create_publishable_channel(session, workspace_id=workspace_id)
    item = QueueItem(
        title=title,
        content=content,
        status=status,
        channel_id=channel.id,
        workspace_id=workspace_id,
    )
    session.add(item)
    await session.flush()
    await session.refresh(item)
    item.channel = channel
    return item


async def create_attempt(
    session: AsyncSession,
    queue_id,
    *,
    attempt_number: int = 1,
    status: str = "started",
    content_hash: str = VALID_CONTENT_HASH,
    expires_at: datetime | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
    provider_chat_id: str | None = None,
    provider_message_id: int | None = None,
    occurred_at: datetime | None = None,
) -> QueuePublishAttempt:
    now = datetime.now(UTC)
    if status == "succeeded":
        provider_chat_id = provider_chat_id or "@testchat"
        provider_message_id = provider_message_id if provider_message_id is not None else 1001
        error_code = None
        error_message = None
    elif status == "failed":
        error_code = error_code or "transport_error"
        error_message = error_message or "publish failed"
        provider_chat_id = None
        provider_message_id = None
    else:
        error_code = None
        error_message = None
        provider_chat_id = None
        provider_message_id = None

    attempt = QueuePublishAttempt(
        queue_id=queue_id,
        attempt_number=attempt_number,
        provider="telegram",
        status=status,
        content_hash=content_hash,
        idempotency_expires_at=expires_at or (now + timedelta(hours=24)),
        error_code=error_code,
        error_message=error_message,
        provider_chat_id=provider_chat_id,
        provider_message_id=provider_message_id,
        occurred_at=occurred_at or now,
    )
    session.add(attempt)
    await session.flush()
    await session.refresh(attempt)
    return attempt
