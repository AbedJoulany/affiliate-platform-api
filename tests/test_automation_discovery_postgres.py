"""PostgreSQL integration coverage for the Phase 6B discovery preview."""
from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from alembic import command
from app.core.enums import ProductStatus, QueueStatus, UserRole
from app.models.automation_policy import AutomationPolicy
from app.models.product import Product
from app.models.queue import QueueItem, QueuePublishAttempt
from app.services.automation_discovery import AutomationDiscoveryService

POSTGRES_URL = os.environ.get("TEST_POSTGRES_URL", "")
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not POSTGRES_URL, reason="Requires isolated TEST_POSTGRES_URL"),
]


@pytest.fixture(scope="module")
def postgres_discovery_migrated():
    """Ensure the disposable database has the Phase 6B schema at revision 020."""
    if not POSTGRES_URL:
        pytest.skip("Requires isolated PostgreSQL")

    config = Config("alembic.ini")
    command.upgrade(config, "020")
    yield


@pytest.fixture
async def pg_db(postgres_discovery_migrated):
    engine = create_async_engine(POSTGRES_URL, pool_size=5, max_overflow=5)
    sessions = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    try:
        yield engine, sessions
    finally:
        await engine.dispose()


async def _workspace(sessions):
    from app.models.workspace import Workspace

    async with sessions() as session:
        workspace = Workspace(name=f"PG discovery test {uuid4().hex}")
        session.add(workspace)
        await session.commit()
        return workspace.id


async def _policy(sessions, workspace_id: UUID, **values):
    async with sessions() as session:
        policy = AutomationPolicy(workspace_id=workspace_id, revision=1, **values)
        session.add(policy)
        await session.commit()


async def _product(
    sessions,
    *,
    product_id: str,
    title: str,
    status: ProductStatus = ProductStatus.ACTIVE,
    price: str = "10.00",
    rating: str = "4.50",
    sales: int = 100,
    discount: str = "10.00",
    commission: str | None = "5.00",
) -> UUID:
    async with sessions() as session:
        product = Product(
            aliexpress_product_id=product_id,
            title=title,
            price=Decimal(price),
            discount=Decimal(discount),
            rating=Decimal(rating),
            sales=sales,
            reviews=10,
            image_url="https://example.com/image.jpg",
            product_url="https://example.com/product",
            affiliate_url=f"https://affiliate.example/{product_id}",
            commission_rate=(Decimal(commission) if commission is not None else None),
            status=status,
        )
        session.add(product)
        await session.commit()
        await session.refresh(product)
        return product.id


async def _queue_item(
    sessions,
    workspace_id: UUID,
    product_id: UUID,
    *,
    status: QueueStatus,
    published_at: datetime | None = None,
) -> UUID:
    async with sessions() as session:
        item = QueueItem(
            workspace_id=workspace_id,
            product_id=product_id,
            content="Postgres discovery test",
            status=status,
            published_at=published_at,
        )
        session.add(item)
        await session.commit()
        await session.refresh(item)
        return item.id


async def _attempt(
    sessions,
    queue_id: UUID,
    *,
    number: int,
    status: str,
    occurred_at: datetime,
) -> None:
    async with sessions() as session:
        session.add(
            QueuePublishAttempt(
                queue_id=queue_id,
                attempt_number=number,
                provider="facebook",
                status=status,
                content_hash=f"{number:064x}"[-64:],
                idempotency_expires_at=occurred_at + timedelta(hours=1),
                occurred_at=occurred_at,
                error_code=None if status == "succeeded" else "test_error",
                error_message=None if status == "succeeded" else "test failure",
                provider_message_ref="post-ref" if status == "succeeded" else None,
            )
        )
        await session.commit()


async def _preview(sessions, workspace_id: UUID):
    async with sessions() as session:
        return await AutomationDiscoveryService(session).preview(
            SimpleNamespace(role=UserRole.ADMIN),
            workspace_id,
        )


async def test_postgres_keyword_prefilter_finds_matches_beyond_initial_slice(pg_db):
    _, sessions = pg_db
    workspace_id = await _workspace(sessions)
    marker = f"pg-tail-{uuid4().hex[:8]}"
    await _policy(sessions, workspace_id, keywords=marker, products_per_run=2)

    async with sessions() as session:
        for index in range(1000):
            session.add(
                Product(
                    aliexpress_product_id=f"pg-prefix-{uuid4().hex}-{index:04d}",
                    title=f"nonmatching {index}",
                    price=Decimal("10.00"),
                    discount=Decimal("10.00"),
                    rating=Decimal("4.50"),
                    sales=100,
                    reviews=10,
                    image_url="https://example.com/image.jpg",
                    product_url="https://example.com/product",
                    affiliate_url=f"https://affiliate.example/prefix/{index}",
                    commission_rate=Decimal("5.00"),
                    status=ProductStatus.ACTIVE,
                )
            )
        matches = []
        for index in range(2):
            product = Product(
                aliexpress_product_id=f"pg-tail-{index:04d}-{uuid4().hex}",
                title=f"{marker} matching {index}",
                price=Decimal("10.00"),
                discount=Decimal("10.00"),
                rating=Decimal("4.50"),
                sales=100,
                reviews=10,
                image_url="https://example.com/image.jpg",
                product_url="https://example.com/product",
                affiliate_url=f"https://affiliate.example/tail/{index}",
                commission_rate=Decimal("5.00"),
                status=ProductStatus.ACTIVE,
            )
            session.add(product)
            matches.append(product)
        await session.commit()
        matching_ids = [product.id for product in matches]

    result = await _preview(sessions, workspace_id)

    assert [item.product_id for item in result.selected_products] == matching_ids
    assert result.database_candidates_inspected == 2
    assert result.candidates_inspected == 2
    assert result.keyword_matches == 2
    assert result.truncated is False


async def test_postgres_filters_boundaries_cap_and_deterministic_order(pg_db):
    _, sessions = pg_db
    workspace_id = await _workspace(sessions)
    marker = f"pg-cap-{uuid4().hex[:8]}"
    await _policy(
        sessions,
        workspace_id,
        keywords=marker,
        min_price=Decimal("10.00"),
        max_price=Decimal("10.00"),
        min_rating=Decimal("4.50"),
        min_orders=100,
        min_discount=Decimal("10.00"),
        min_commission=Decimal("5.00"),
        max_commission=Decimal("5.00"),
        products_per_run=2,
    )
    await _product(
        sessions,
        product_id=f"pg-boundary-{uuid4().hex}",
        title=f"{marker} exact",
    )
    low_price_id = await _product(
        sessions,
        product_id=f"pg-boundary-low-{uuid4().hex}",
        title=f"{marker} low",
        price="9.99",
    )
    inactive_id = await _product(
        sessions,
        product_id=f"pg-boundary-inactive-{uuid4().hex}",
        title=f"{marker} inactive",
        status=ProductStatus.INACTIVE,
    )
    for index in range(1001):
        await _product(
            sessions,
            product_id=f"pg-cap-{marker}-{index:04d}",
            title=f"{marker} cap {index}",
        )

    first = await _preview(sessions, workspace_id)
    second = await _preview(sessions, workspace_id)

    assert first.truncated is True
    assert first.database_candidates_inspected == 1001
    assert first.candidates_inspected == 1000
    assert first.keyword_matches == 1000
    assert first.selected_count == 2
    selected_ids = {item.product_id for item in first.selected_products}
    assert low_price_id not in selected_ids
    assert inactive_id not in selected_ids
    assert [item.product_id for item in first.selected_products] == [
        item.product_id for item in second.selected_products
    ]


async def test_postgres_workspace_history_and_seven_day_boundary(pg_db):
    _, sessions = pg_db
    workspace_id = await _workspace(sessions)
    other_workspace_id = await _workspace(sessions)
    marker = f"pg-history-{uuid4().hex[:8]}"
    await _policy(sessions, workspace_id, keywords=marker, products_per_run=20)

    other_workspace_product = await _product(
        sessions,
        product_id=f"pg-other-{uuid4().hex}",
        title=f"{marker} other workspace",
    )
    await _queue_item(
        sessions,
        other_workspace_id,
        other_workspace_product,
        status=QueueStatus.QUEUED,
    )

    recent_product = await _product(
        sessions,
        product_id=f"pg-recent-{uuid4().hex}",
        title=f"{marker} recent",
    )
    await _queue_item(
        sessions,
        workspace_id,
        recent_product,
        status=QueueStatus.PUBLISHED,
        published_at=datetime.now(UTC) - timedelta(days=1),
    )

    boundary_product = await _product(
        sessions,
        product_id=f"pg-boundary-old-{uuid4().hex}",
        title=f"{marker} boundary old",
    )
    await _queue_item(
        sessions,
        workspace_id,
        boundary_product,
        status=QueueStatus.PUBLISHED,
        published_at=datetime.now(UTC) - timedelta(days=7, seconds=5),
    )

    ambiguous_product = await _product(
        sessions,
        product_id=f"pg-ambiguous-{uuid4().hex}",
        title=f"{marker} ambiguous",
    )
    ambiguous_queue = await _queue_item(
        sessions,
        workspace_id,
        ambiguous_product,
        status=QueueStatus.FAILED,
    )
    await _attempt(
        sessions,
        ambiguous_queue,
        number=1,
        status="ambiguous",
        occurred_at=datetime.now(UTC) - timedelta(days=30),
    )

    resolved_product = await _product(
        sessions,
        product_id=f"pg-resolved-{uuid4().hex}",
        title=f"{marker} resolved",
    )
    resolved_queue = await _queue_item(
        sessions,
        workspace_id,
        resolved_product,
        status=QueueStatus.FAILED,
    )
    resolved_at = datetime.now(UTC) - timedelta(days=30)
    await _attempt(
        sessions,
        resolved_queue,
        number=1,
        status="ambiguous",
        occurred_at=resolved_at,
    )
    await _attempt(
        sessions,
        resolved_queue,
        number=2,
        status="failed",
        occurred_at=resolved_at + timedelta(minutes=1),
    )

    result = await _preview(sessions, workspace_id)
    selected_ids = {item.product_id for item in result.selected_products}

    assert other_workspace_product in selected_ids
    assert boundary_product in selected_ids
    assert resolved_product in selected_ids
    assert recent_product not in selected_ids
    assert ambiguous_product not in selected_ids
