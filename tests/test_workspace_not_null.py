"""Phase E Task 8 — tenant workspace_id NOT NULL closeout."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import QueueStatus
from app.models.channel import TelegramChannel
from app.models.queue import QueueItem
from app.models.workspace import Workspace
from tests.factories.queue_publishing import (
    create_publishable_channel,
    create_publishable_queue_item,
)

_MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "013_workspace_id_not_null.py"
)


def _load_migration_013():
    spec = importlib.util.spec_from_file_location("migration_013", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def _create_workspace(session: AsyncSession) -> Workspace:
    workspace = Workspace(name=f"Task 8 workspace {uuid4().hex[:8]}")
    session.add(workspace)
    await session.flush()
    return workspace


@pytest.mark.asyncio
async def test_queue_item_without_workspace_id_is_rejected(session: AsyncSession):
    session.add(QueueItem(title="No workspace", content="content", status=QueueStatus.DRAFT))
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_telegram_channel_without_workspace_id_is_rejected(session: AsyncSession):
    session.add(TelegramChannel(telegram_channel_id=f"@nows{uuid4().hex[:8]}"))
    with pytest.raises(IntegrityError):
        await session.flush()


@pytest.mark.asyncio
async def test_queue_item_with_workspace_id_is_accepted(session: AsyncSession):
    workspace = await _create_workspace(session)
    item = QueueItem(
        title="Owned queue",
        content="content",
        status=QueueStatus.DRAFT,
        workspace_id=workspace.id,
    )
    session.add(item)
    await session.flush()
    await session.refresh(item)
    assert item.workspace_id == workspace.id


@pytest.mark.asyncio
async def test_telegram_channel_with_workspace_id_is_accepted(session: AsyncSession):
    workspace = await _create_workspace(session)
    channel = TelegramChannel(
        telegram_channel_id=f"@owned{uuid4().hex[:8]}",
        workspace_id=workspace.id,
    )
    session.add(channel)
    await session.flush()
    await session.refresh(channel)
    assert channel.workspace_id == workspace.id


@pytest.mark.asyncio
async def test_publish_factory_assigns_a_workspace(session: AsyncSession):
    item = await create_publishable_queue_item(session)
    channel = await create_publishable_channel(session)
    assert item.workspace_id is not None
    assert channel.workspace_id is not None
    stored_item = await session.get(QueueItem, item.id)
    stored_channel = await session.get(TelegramChannel, channel.id)
    assert stored_item is not None
    assert stored_channel is not None
    assert stored_item.workspace_id == item.workspace_id
    assert stored_channel.workspace_id == channel.workspace_id


def test_migration_013_fails_closed_when_null_counts_exist():
    migration = _load_migration_013()
    with pytest.raises(RuntimeError, match="campaigns=2") as exc_info:
        migration.raise_if_null_workspace_rows(
            {"campaigns": 2, "queue_items": 0, "telegram_channels": 1}
        )
    message = str(exc_info.value)
    assert "telegram_channels=1" in message
    assert "No automatic backfill" in message


def test_migration_013_allows_upgrade_when_all_counts_are_zero():
    migration = _load_migration_013()
    migration.raise_if_null_workspace_rows(
        {"campaigns": 0, "queue_items": 0, "telegram_channels": 0}
    )


def test_migration_013_revises_012():
    migration = _load_migration_013()
    assert migration.revision == "013"
    assert migration.down_revision == "012"
