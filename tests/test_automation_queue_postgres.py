"""PostgreSQL verification for Phase 8B Queue scheduling persistence."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from alembic import command
from app.core.enums import BotPermissionStatus, ProductStatus, QueueStatus
from app.models.channel import TelegramChannel
from app.models.product import Product
from app.models.queue import QueueItem
from app.models.workspace import Workspace
from app.repositories.queue import QueueRepository
from app.schemas.queue import QueueCreate
from app.services.queue import QueueService

POSTGRES_URL = os.environ.get("TEST_POSTGRES_URL", "")
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not POSTGRES_URL, reason="Requires isolated TEST_POSTGRES_URL"),
]


@pytest.fixture(scope="module")
def postgres_migrated():
    if not POSTGRES_URL:
        pytest.skip("Requires isolated PostgreSQL")
    assert os.environ.get("DATABASE_URL") == POSTGRES_URL
    command.upgrade(Config("alembic.ini"), "020")
    yield


@pytest.fixture
async def pg_session_factory(postgres_migrated):
    engine = create_async_engine(POSTGRES_URL, pool_size=5, max_overflow=5)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    finally:
        await engine.dispose()


async def _workspace(session_factory, name: str) -> Workspace:
    async with session_factory() as session:
        workspace = Workspace(name=name)
        session.add(workspace)
        await session.commit()
        await session.refresh(workspace)
        return workspace


async def test_destination_history_is_workspace_and_provider_scoped(pg_session_factory):
    first = await _workspace(pg_session_factory, f"Phase 8B first {uuid4().hex}")
    second = await _workspace(pg_session_factory, f"Phase 8B second {uuid4().hex}")
    first_channel_id = uuid4()
    second_channel_id = uuid4()
    now = datetime.now(UTC).replace(microsecond=0)

    async with pg_session_factory() as session:
        session.add_all(
            [
                TelegramChannel(
                    id=first_channel_id,
                    workspace_id=first.id,
                    telegram_channel_id=f"pg-8b-first-{uuid4().hex}",
                    title="First",
                    bot_permission_status=BotPermissionStatus.GRANTED,
                    can_post_messages=True,
                    can_edit_messages=True,
                    can_delete_messages=True,
                    is_active=True,
                ),
                TelegramChannel(
                    id=second_channel_id,
                    workspace_id=second.id,
                    telegram_channel_id=f"pg-8b-second-{uuid4().hex}",
                    title="Second",
                    bot_permission_status=BotPermissionStatus.GRANTED,
                    can_post_messages=True,
                    can_edit_messages=True,
                    can_delete_messages=True,
                    is_active=True,
                ),
                QueueItem(
                    workspace_id=first.id,
                    provider="telegram",
                    channel_id=first_channel_id,
                    content="scheduled",
                    status=QueueStatus.SCHEDULED,
                    scheduled_at=now + timedelta(hours=1),
                ),
                QueueItem(
                    workspace_id=first.id,
                    provider="telegram",
                    channel_id=first_channel_id,
                    content="published",
                    status=QueueStatus.PUBLISHED,
                    published_at=now + timedelta(hours=2),
                ),
                QueueItem(
                    workspace_id=second.id,
                    provider="telegram",
                    channel_id=second_channel_id,
                    content="other workspace",
                    status=QueueStatus.SCHEDULED,
                    scheduled_at=now + timedelta(hours=1),
                ),
            ]
        )
        await session.commit()

    async with pg_session_factory() as session:
        timestamps = await QueueRepository(session).list_destination_publishing_timestamps(
            workspace_id=first.id,
            provider="telegram",
            destination_id=first_channel_id,
            start_utc=now,
            end_utc=now + timedelta(days=1),
        )
    assert sorted(timestamps) == [now + timedelta(hours=1), now + timedelta(hours=2)]


async def test_automation_queue_creation_persists_scheduled_item(pg_session_factory):
    workspace = await _workspace(pg_session_factory, f"Phase 8B queue {uuid4().hex}")
    channel_id = uuid4()
    product_id = uuid4()
    affiliate_url = "https://affiliate.example/postgres"
    async with pg_session_factory() as session:
        session.add(
            TelegramChannel(
                id=channel_id,
                workspace_id=workspace.id,
                telegram_channel_id=f"pg-8b-queue-{uuid4().hex}",
                title="Queue channel",
                bot_permission_status=BotPermissionStatus.GRANTED,
                can_post_messages=True,
                can_edit_messages=True,
                can_delete_messages=True,
                is_active=True,
            )
        )
        session.add(
            Product(
                id=product_id,
                aliexpress_product_id=f"pg-8b-product-{uuid4().hex}",
                title="Postgres product",
                price=Decimal("10.00"),
                discount=Decimal("10.00"),
                rating=Decimal("4.50"),
                sales=100,
                reviews=10,
                image_url="https://example.com/image.jpg",
                product_url="https://example.com/product",
                affiliate_url=affiliate_url,
                commission_rate=Decimal("5.00"),
                status=ProductStatus.ACTIVE,
            )
        )
        await session.commit()

    async with pg_session_factory() as session:
        item = await QueueService(session).create_automation_scheduled(
            QueueCreate(
                content="Postgres scheduled content",
                status=QueueStatus.SCHEDULED,
                scheduled_at=datetime.now(UTC) + timedelta(hours=1),
                provider="telegram",
                channel_id=channel_id,
                product_id=product_id,
                button_text="Buy",
                button_url=affiliate_url,
            ),
            workspace.id,
            expected_affiliate_url=affiliate_url,
        )
        await session.commit()
        assert item.status == QueueStatus.SCHEDULED
        assert item.button_url == affiliate_url

    async with pg_session_factory() as session:
        result = await session.get(QueueItem, item.id)
        assert result is not None
        assert result.status == QueueStatus.SCHEDULED
