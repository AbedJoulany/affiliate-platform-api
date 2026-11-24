"""PostgreSQL verification for Phase 8B Queue scheduling persistence."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, time, timedelta
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from alembic.config import Config
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from alembic import command
from app.core.enums import BotPermissionStatus, ProductStatus, QueueStatus
from app.models.channel import TelegramChannel
from app.models.product import Product
from app.models.queue import QueueItem
from app.models.workspace import Workspace
from app.repositories.queue import QueueRepository
from app.schemas.queue import QueueCreate, QueueUpdate
from app.services.exceptions import ConflictError
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


def _telegram_channel(workspace_id, channel_id, *, title: str) -> TelegramChannel:
    return TelegramChannel(
        id=channel_id,
        workspace_id=workspace_id,
        telegram_channel_id=f"pg-9b3-{uuid4().hex}",
        title=title,
        bot_permission_status=BotPermissionStatus.GRANTED,
        can_post_messages=True,
        can_edit_messages=True,
        can_delete_messages=True,
        is_active=True,
    )


def _active_product(product_id, affiliate_url: str) -> Product:
    return Product(
        id=product_id,
        aliexpress_product_id=f"pg-9b3-product-{uuid4().hex}",
        title="Reservation test product",
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
                    scheduled_at=now - timedelta(days=1),
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
            timezone_name="UTC",
            preferred_time_local=datetime.now(UTC).time().replace(second=0, microsecond=0),
            daily_limit=1,
        )
        await session.commit()
        assert item.status == QueueStatus.SCHEDULED
        assert item.button_url == affiliate_url

    async with pg_session_factory() as session:
        result = await session.get(QueueItem, item.id)
        assert result is not None
        assert result.status == QueueStatus.SCHEDULED


async def test_published_timestamp_wins_when_schedule_crosses_local_day(
    pg_session_factory,
):
    workspace = await _workspace(pg_session_factory, f"Phase 8B timestamp {uuid4().hex}")
    channel_id = uuid4()
    window_start = datetime(2026, 11, 21, 22, 0, tzinfo=UTC)
    window_end = datetime(2026, 11, 22, 22, 0, tzinfo=UTC)
    scheduled_at = window_start - timedelta(minutes=30)
    published_at = window_end - timedelta(minutes=30)

    async with pg_session_factory() as session:
        session.add(
            TelegramChannel(
                id=channel_id,
                workspace_id=workspace.id,
                telegram_channel_id=f"pg-8b-midnight-{uuid4().hex}",
                title="Midnight",
                bot_permission_status=BotPermissionStatus.GRANTED,
                can_post_messages=True,
                can_edit_messages=True,
                can_delete_messages=True,
                is_active=True,
            )
        )
        session.add(
            QueueItem(
                workspace_id=workspace.id,
                provider="telegram",
                channel_id=channel_id,
                content="delayed publication",
                status=QueueStatus.PUBLISHED,
                scheduled_at=scheduled_at,
                published_at=published_at,
            )
        )
        await session.commit()

    async with pg_session_factory() as session:
        timestamps = await QueueRepository(session).list_destination_publishing_timestamps(
            workspace_id=workspace.id,
            provider="telegram",
            destination_id=channel_id,
            start_utc=window_start,
            end_utc=window_end,
        )
    assert timestamps == [published_at]


async def test_concurrent_different_products_respect_destination_daily_limit(
    pg_session_factory,
):
    workspace = await _workspace(pg_session_factory, f"Phase 8B concurrent {uuid4().hex}")
    channel_id = uuid4()
    product_ids = [uuid4(), uuid4()]
    now_local = datetime.now(UTC).astimezone(ZoneInfo("UTC"))
    preferred_time = (now_local + timedelta(days=1, hours=1)).time().replace(
        second=0,
        microsecond=0,
    )

    async with pg_session_factory() as session:
        session.add(
            TelegramChannel(
                id=channel_id,
                workspace_id=workspace.id,
                telegram_channel_id=f"pg-8b-concurrent-{uuid4().hex}",
                title="Concurrent",
                bot_permission_status=BotPermissionStatus.GRANTED,
                can_post_messages=True,
                can_edit_messages=True,
                can_delete_messages=True,
                is_active=True,
            )
        )
        session.add_all(
            [
                Product(
                    id=product_id,
                    aliexpress_product_id=f"pg-8b-concurrent-product-{uuid4().hex}",
                    title=f"Concurrent product {index}",
                    price=Decimal("10.00"),
                    discount=Decimal("10.00"),
                    rating=Decimal("4.50"),
                    sales=100,
                    reviews=10,
                    image_url="https://example.com/image.jpg",
                    product_url="https://example.com/product",
                    affiliate_url=f"https://affiliate.example/{product_id}",
                    commission_rate=Decimal("5.00"),
                    status=ProductStatus.ACTIVE,
                )
                for index, product_id in enumerate(product_ids, start=1)
            ]
        )
        await session.commit()

    async def schedule(product_id):
        async with pg_session_factory() as session:
            try:
                item = await QueueService(session).create_automation_scheduled(
                    QueueCreate(
                        content="Concurrent content",
                        status=QueueStatus.SCHEDULED,
                        scheduled_at=datetime.now(UTC) + timedelta(days=1),
                        provider="telegram",
                        channel_id=channel_id,
                        product_id=product_id,
                        button_text="Buy",
                        button_url=f"https://affiliate.example/{product_id}",
                    ),
                    workspace.id,
                    expected_affiliate_url=f"https://affiliate.example/{product_id}",
                    timezone_name="UTC",
                    preferred_time_local=preferred_time,
                    daily_limit=1,
                )
                await session.commit()
                return item
            except Exception:
                await session.rollback()
                return None

    items = await asyncio.gather(*(schedule(product_id) for product_id in product_ids))
    scheduled = [item for item in items if item is not None]
    assert len(scheduled) == 2
    assert len({item.scheduled_at.date() for item in scheduled}) == 2


async def test_different_workspaces_can_allocate_same_local_day(pg_session_factory):
    first = await _workspace(pg_session_factory, f"Phase 8B workspace A {uuid4().hex}")
    second = await _workspace(pg_session_factory, f"Phase 8B workspace B {uuid4().hex}")
    channel_ids = [uuid4(), uuid4()]
    product_ids = [uuid4(), uuid4()]
    preferred_time = time(23, 30)

    async with pg_session_factory() as session:
        for workspace, channel_id, product_id in zip(
            (first, second), channel_ids, product_ids, strict=True
        ):
            session.add(
                TelegramChannel(
                    id=channel_id,
                    workspace_id=workspace.id,
                    telegram_channel_id=f"pg-8b-workspace-{uuid4().hex}",
                    title="Workspace channel",
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
                    aliexpress_product_id=f"pg-8b-workspace-product-{uuid4().hex}",
                    title="Workspace product",
                    price=Decimal("10.00"),
                    discount=Decimal("10.00"),
                    rating=Decimal("4.50"),
                    sales=100,
                    reviews=10,
                    image_url="https://example.com/image.jpg",
                    product_url="https://example.com/product",
                    affiliate_url=f"https://affiliate.example/{product_id}",
                    commission_rate=Decimal("5.00"),
                    status=ProductStatus.ACTIVE,
                )
            )
        await session.commit()

    async def schedule(workspace, channel_id, product_id):
        async with pg_session_factory() as session:
            item = await QueueService(session).create_automation_scheduled(
                QueueCreate(
                    content="Workspace content",
                    status=QueueStatus.SCHEDULED,
                    scheduled_at=datetime.now(UTC) + timedelta(days=1),
                    provider="telegram",
                    channel_id=channel_id,
                    product_id=product_id,
                    button_text="Buy",
                    button_url=f"https://affiliate.example/{product_id}",
                ),
                workspace.id,
                expected_affiliate_url=f"https://affiliate.example/{product_id}",
                timezone_name="UTC",
                preferred_time_local=preferred_time,
                daily_limit=1,
            )
            await session.commit()
            return item

    items = await asyncio.gather(
        schedule(first, channel_ids[0], product_ids[0]),
        schedule(second, channel_ids[1], product_ids[1]),
    )
    assert len(items) == 2
    assert items[0].scheduled_at.date() == items[1].scheduled_at.date()


async def test_same_product_concurrency_allows_only_one_queue_item(pg_session_factory):
    workspace = await _workspace(pg_session_factory, f"Phase 8B same product {uuid4().hex}")
    channel_id = uuid4()
    product_id = uuid4()
    affiliate_url = f"https://affiliate.example/{product_id}"
    async with pg_session_factory() as session:
        session.add(
            TelegramChannel(
                id=channel_id,
                workspace_id=workspace.id,
                telegram_channel_id=f"pg-8b-same-product-{uuid4().hex}",
                title="Same product",
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
                aliexpress_product_id=f"pg-8b-same-product-{uuid4().hex}",
                title="Same product",
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

    async def schedule():
        async with pg_session_factory() as session:
            try:
                item = await QueueService(session).create_automation_scheduled(
                    QueueCreate(
                        content="Same product content",
                        status=QueueStatus.SCHEDULED,
                        scheduled_at=datetime.now(UTC) + timedelta(days=1),
                        provider="telegram",
                        channel_id=channel_id,
                        product_id=product_id,
                        button_text="Buy",
                        button_url=affiliate_url,
                    ),
                    workspace.id,
                    expected_affiliate_url=affiliate_url,
                    timezone_name="UTC",
                    preferred_time_local=time(23, 30),
                    daily_limit=1,
                )
                await session.commit()
                return item
            except Exception:
                await session.rollback()
                return None

    items = await asyncio.gather(schedule(), schedule())
    assert sum(item is not None for item in items) == 1

    async with pg_session_factory() as session:
        result = await session.execute(
            select(QueueItem).where(
                QueueItem.workspace_id == workspace.id,
                QueueItem.product_id == product_id,
            )
        )
        assert len(result.scalars().all()) == 1


async def test_different_destinations_have_independent_daily_capacity(
    pg_session_factory,
):
    workspace = await _workspace(pg_session_factory, f"Phase 8B destinations {uuid4().hex}")
    channel_ids = [uuid4(), uuid4()]
    product_ids = [uuid4(), uuid4()]
    preferred_time = time(23, 30)
    async with pg_session_factory() as session:
        for index, (channel_id, product_id) in enumerate(
            zip(channel_ids, product_ids, strict=True), start=1
        ):
            session.add(
                TelegramChannel(
                    id=channel_id,
                    workspace_id=workspace.id,
                    telegram_channel_id=f"pg-8b-destination-{uuid4().hex}",
                    title=f"Destination {index}",
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
                    aliexpress_product_id=f"pg-8b-destination-product-{uuid4().hex}",
                    title=f"Destination product {index}",
                    price=Decimal("10.00"),
                    discount=Decimal("10.00"),
                    rating=Decimal("4.50"),
                    sales=100,
                    reviews=10,
                    image_url="https://example.com/image.jpg",
                    product_url="https://example.com/product",
                    affiliate_url=f"https://affiliate.example/{product_id}",
                    commission_rate=Decimal("5.00"),
                    status=ProductStatus.ACTIVE,
                )
            )
        await session.commit()

    async def schedule(channel_id, product_id):
        async with pg_session_factory() as session:
            item = await QueueService(session).create_automation_scheduled(
                QueueCreate(
                    content="Destination content",
                    status=QueueStatus.SCHEDULED,
                    scheduled_at=datetime.now(UTC) + timedelta(days=1),
                    provider="telegram",
                    channel_id=channel_id,
                    product_id=product_id,
                    button_text="Buy",
                    button_url=f"https://affiliate.example/{product_id}",
                ),
                workspace.id,
                expected_affiliate_url=f"https://affiliate.example/{product_id}",
                timezone_name="UTC",
                preferred_time_local=preferred_time,
                daily_limit=1,
            )
            await session.commit()
            return item

    items = await asyncio.gather(
        schedule(channel_ids[0], product_ids[0]),
        schedule(channel_ids[1], product_ids[1]),
    )
    assert len(items) == 2
    assert items[0].scheduled_at.date() == items[1].scheduled_at.date()


async def test_automation_capacity_counts_publication_earlier_on_local_day(
    pg_session_factory,
    monkeypatch,
):
    workspace = await _workspace(pg_session_factory, f"Phase 9B.3 published {uuid4().hex}")
    channel_id = uuid4()
    product_id = uuid4()
    affiliate_url = f"https://affiliate.example/{product_id}"
    frozen_now = datetime(2026, 11, 21, 16, 0, tzinfo=UTC)
    timezone_name = "America/New_York"
    timezone = ZoneInfo(timezone_name)
    local_today = frozen_now.astimezone(timezone).date()
    published_at = datetime(2026, 11, 21, 13, 0, tzinfo=UTC)

    async with pg_session_factory() as session:
        session.add(_telegram_channel(workspace.id, channel_id, title="Capacity"))
        session.add(_active_product(product_id, affiliate_url))
        session.add(
            QueueItem(
                workspace_id=workspace.id,
                provider="telegram",
                channel_id=channel_id,
                content="Published earlier today",
                status=QueueStatus.PUBLISHED,
                scheduled_at=published_at - timedelta(days=1),
                published_at=published_at,
            )
        )
        await session.commit()

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return frozen_now if tz is None else frozen_now.astimezone(tz)

    monkeypatch.setattr("app.services.queue.datetime", FrozenDateTime)
    async with pg_session_factory() as session:
        item = await QueueService(session).create_automation_scheduled(
            QueueCreate(
                content="Automation content",
                status=QueueStatus.SCHEDULED,
                scheduled_at=frozen_now + timedelta(days=1),
                provider="telegram",
                channel_id=channel_id,
                product_id=product_id,
                button_text="Buy",
                button_url=affiliate_url,
            ),
            workspace.id,
            expected_affiliate_url=affiliate_url,
            timezone_name=timezone_name,
            preferred_time_local=time(18, 0),
            daily_limit=1,
        )
        await session.commit()

    assert item.scheduled_at.astimezone(timezone).date() > local_today


async def test_manual_queue_creation_reserves_capacity_before_automation(
    pg_session_factory,
    monkeypatch,
):
    workspace = await _workspace(pg_session_factory, f"Phase 9B.3 manual create {uuid4().hex}")
    channel_id = uuid4()
    manual_product_id = uuid4()
    automation_product_id = uuid4()
    manual_affiliate = f"https://affiliate.example/{manual_product_id}"
    automation_affiliate = f"https://affiliate.example/{automation_product_id}"
    frozen_now = datetime(2026, 11, 21, 16, 0, tzinfo=UTC)
    timezone_name = "America/New_York"
    timezone = ZoneInfo(timezone_name)
    local_today = frozen_now.astimezone(timezone).date()
    manual_slot = datetime.combine(
        local_today,
        time(18, 0),
        tzinfo=timezone,
    ).astimezone(UTC)

    async with pg_session_factory() as session:
        session.add(_telegram_channel(workspace.id, channel_id, title="Shared capacity"))
        session.add_all(
            [
                _active_product(manual_product_id, manual_affiliate),
                _active_product(automation_product_id, automation_affiliate),
            ]
        )
        await session.commit()

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return frozen_now if tz is None else frozen_now.astimezone(tz)

    monkeypatch.setattr("app.services.queue.datetime", FrozenDateTime)
    manual_created = asyncio.Event()
    allow_manual_commit = asyncio.Event()

    async def create_manual_item():
        async with pg_session_factory() as session:
            item = await QueueService(session).create(
                QueueCreate(
                    content="Manual scheduled content",
                    status=QueueStatus.SCHEDULED,
                    scheduled_at=manual_slot,
                    provider="telegram",
                    channel_id=channel_id,
                    product_id=manual_product_id,
                    button_text="Buy",
                    button_url=manual_affiliate,
                ),
                workspace.id,
            )
            manual_created.set()
            await allow_manual_commit.wait()
            await session.commit()
            return item

    async def create_automation_item():
        async with pg_session_factory() as session:
            item = await QueueService(session).create_automation_scheduled(
                QueueCreate(
                    content="Automated scheduled content",
                    status=QueueStatus.SCHEDULED,
                    scheduled_at=frozen_now + timedelta(days=1),
                    provider="telegram",
                    channel_id=channel_id,
                    product_id=automation_product_id,
                    button_text="Buy",
                    button_url=automation_affiliate,
                ),
                workspace.id,
                expected_affiliate_url=automation_affiliate,
                timezone_name=timezone_name,
                preferred_time_local=time(18, 0),
                daily_limit=1,
            )
            await session.commit()
            return item

    manual_task = asyncio.create_task(create_manual_item())
    await asyncio.wait_for(manual_created.wait(), timeout=5)
    automation_task = asyncio.create_task(create_automation_item())
    try:
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(asyncio.shield(automation_task), timeout=0.1)
    finally:
        allow_manual_commit.set()
    manual_item, automation_item = await asyncio.gather(manual_task, automation_task)

    assert manual_item.scheduled_at == manual_slot
    assert automation_item.scheduled_at.astimezone(timezone).date() > local_today


async def test_concurrent_manual_creation_blocks_automation_product_across_destinations(
    pg_session_factory,
):
    workspace = await _workspace(pg_session_factory, f"Phase 9B.3 manual product {uuid4().hex}")
    channel_ids = [uuid4(), uuid4()]
    product_id = uuid4()
    affiliate_url = f"https://affiliate.example/{product_id}"
    async with pg_session_factory() as session:
        session.add_all(
            [
                _telegram_channel(workspace.id, channel_ids[0], title="Manual destination"),
                _telegram_channel(workspace.id, channel_ids[1], title="Automation destination"),
                _active_product(product_id, affiliate_url),
            ]
        )
        await session.commit()

    manual_created = asyncio.Event()
    allow_manual_commit = asyncio.Event()

    async def create_manual_item():
        async with pg_session_factory() as session:
            item = await QueueService(session).create(
                QueueCreate(
                    content="Manual product post",
                    status=QueueStatus.SCHEDULED,
                    scheduled_at=datetime.now(UTC) + timedelta(days=1),
                    provider="telegram",
                    channel_id=channel_ids[0],
                    product_id=product_id,
                    button_text="Buy",
                    button_url=affiliate_url,
                ),
                workspace.id,
            )
            manual_created.set()
            await allow_manual_commit.wait()
            await session.commit()
            return item

    async def create_automation_item():
        async with pg_session_factory() as session:
            try:
                await QueueService(session).create_automation_scheduled(
                    QueueCreate(
                        content="Automation product post",
                        status=QueueStatus.SCHEDULED,
                        scheduled_at=datetime.now(UTC) + timedelta(days=1),
                        provider="telegram",
                        channel_id=channel_ids[1],
                        product_id=product_id,
                        button_text="Buy",
                        button_url=affiliate_url,
                    ),
                    workspace.id,
                    expected_affiliate_url=affiliate_url,
                    timezone_name="UTC",
                    preferred_time_local=time(23, 30),
                    daily_limit=1,
                )
                await session.commit()
                return False
            except ConflictError:
                await session.rollback()
                return True

    manual_task = asyncio.create_task(create_manual_item())
    await asyncio.wait_for(manual_created.wait(), timeout=5)
    automation_task = asyncio.create_task(create_automation_item())
    try:
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(asyncio.shield(automation_task), timeout=0.1)
    finally:
        allow_manual_commit.set()
    manual_item, automation_rejected = await asyncio.gather(manual_task, automation_task)

    assert manual_item.status == QueueStatus.SCHEDULED
    assert automation_rejected is True


async def test_concurrent_automation_product_reservation_spans_destinations(
    pg_session_factory,
):
    workspace = await _workspace(pg_session_factory, f"Phase 9B.3 destinations {uuid4().hex}")
    channel_ids = [uuid4(), uuid4()]
    product_id = uuid4()
    affiliate_url = f"https://affiliate.example/{product_id}"
    async with pg_session_factory() as session:
        session.add_all(
            [
                _telegram_channel(workspace.id, channel_ids[0], title="Destination one"),
                _telegram_channel(workspace.id, channel_ids[1], title="Destination two"),
                _active_product(product_id, affiliate_url),
            ]
        )
        await session.commit()

    async def schedule(channel_id):
        async with pg_session_factory() as session:
            try:
                item = await QueueService(session).create_automation_scheduled(
                    QueueCreate(
                        content="Concurrent automation content",
                        status=QueueStatus.SCHEDULED,
                        scheduled_at=datetime.now(UTC) + timedelta(days=1),
                        provider="telegram",
                        channel_id=channel_id,
                        product_id=product_id,
                        button_text="Buy",
                        button_url=affiliate_url,
                    ),
                    workspace.id,
                    expected_affiliate_url=affiliate_url,
                    timezone_name="UTC",
                    preferred_time_local=time(23, 30),
                    daily_limit=1,
                )
                await session.commit()
                return item
            except ConflictError:
                await session.rollback()
                return None

    results = await asyncio.gather(*(schedule(channel_id) for channel_id in channel_ids))
    assert sum(item is not None for item in results) == 1


async def test_manual_reschedule_serializes_with_automation_across_destinations(
    pg_session_factory,
    monkeypatch,
):
    workspace = await _workspace(pg_session_factory, f"Phase 9B.3 reschedule {uuid4().hex}")
    channel_ids = [uuid4(), uuid4()]
    product_id = uuid4()
    affiliate_url = f"https://affiliate.example/{product_id}"
    queue_id = uuid4()
    async with pg_session_factory() as session:
        session.add_all(
            [
                _telegram_channel(workspace.id, channel_ids[0], title="Manual destination"),
                _telegram_channel(workspace.id, channel_ids[1], title="Automation destination"),
                _active_product(product_id, affiliate_url),
                QueueItem(
                    id=queue_id,
                    workspace_id=workspace.id,
                    provider="telegram",
                    channel_id=channel_ids[0],
                    product_id=product_id,
                    content="Draft to reschedule",
                    status=QueueStatus.DRAFT,
                ),
            ]
        )
        await session.commit()

    update_reached = asyncio.Event()
    allow_update_commit = asyncio.Event()
    original_update = QueueRepository.update

    async def pause_before_update(repository, item):
        update_reached.set()
        await allow_update_commit.wait()
        return await original_update(repository, item)

    monkeypatch.setattr(QueueRepository, "update", pause_before_update)

    async def reschedule_manually():
        async with pg_session_factory() as session:
            return await QueueService(session).update(
                queue_id,
                QueueUpdate(
                    status=QueueStatus.SCHEDULED,
                    scheduled_at=datetime.now(UTC) + timedelta(days=1),
                ),
                workspace.id,
            )

    async def schedule_automatically():
        async with pg_session_factory() as session:
            try:
                await QueueService(session).create_automation_scheduled(
                    QueueCreate(
                        content="Automation content",
                        status=QueueStatus.SCHEDULED,
                        scheduled_at=datetime.now(UTC) + timedelta(days=1),
                        provider="telegram",
                        channel_id=channel_ids[1],
                        product_id=product_id,
                        button_text="Buy",
                        button_url=affiliate_url,
                    ),
                    workspace.id,
                    expected_affiliate_url=affiliate_url,
                    timezone_name="UTC",
                    preferred_time_local=time(23, 30),
                    daily_limit=1,
                )
                await session.commit()
                return True
            except ConflictError:
                await session.rollback()
                return False

    manual_task = asyncio.create_task(reschedule_manually())
    await asyncio.wait_for(update_reached.wait(), timeout=5)
    automation_task = asyncio.create_task(schedule_automatically())
    try:
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(asyncio.shield(automation_task), timeout=0.1)
    finally:
        allow_update_commit.set()
    manual_item, automation_created = await asyncio.gather(manual_task, automation_task)

    assert manual_item.status == QueueStatus.SCHEDULED
    assert automation_created is False


async def test_manual_reposts_remain_allowed_without_automation_daily_cap(
    pg_session_factory,
):
    workspace = await _workspace(pg_session_factory, f"Phase 9B.3 repost {uuid4().hex}")
    channel_id = uuid4()
    product_id = uuid4()
    affiliate_url = f"https://affiliate.example/{product_id}"
    now = datetime.now(UTC)
    async with pg_session_factory() as session:
        session.add(_telegram_channel(workspace.id, channel_id, title="Manual reposts"))
        session.add(_active_product(product_id, affiliate_url))
        await session.commit()

    async with pg_session_factory() as session:
        service = QueueService(session)
        items = [
            await service.create(
                QueueCreate(
                    content=f"Intentional manual post {index}",
                    status=QueueStatus.SCHEDULED,
                    scheduled_at=now + timedelta(days=1, hours=index),
                    provider="telegram",
                    channel_id=channel_id,
                    product_id=product_id,
                    button_text="Buy",
                    button_url=affiliate_url,
                ),
                workspace.id,
            )
            for index in range(2)
        ]
        await session.commit()

    assert len({item.id for item in items}) == 2
    async with pg_session_factory() as session:
        result = await session.execute(
            select(QueueItem.id).where(
                QueueItem.workspace_id == workspace.id,
                QueueItem.product_id == product_id,
                QueueItem.status == QueueStatus.SCHEDULED,
            )
        )
        assert len(result.scalars().all()) == 2
