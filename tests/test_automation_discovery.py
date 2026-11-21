from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.core.enums import ProductStatus, QueueStatus
from app.core.workspace import WORKSPACE_ID_HEADER
from app.models.automation_policy import AutomationPolicy
from app.models.product import Product
from app.models.queue import QueueItem, QueuePublishAttempt
from tests.conftest import SessionLocal
from tests.test_api_endpoints import API_PREFIX, register_and_login, workspace_auth_headers

PREVIEW = f"{API_PREFIX}/automation/discovery/preview"


async def _create_policy(workspace_id: str, **values) -> None:
    async with SessionLocal() as session:
        session.add(
            AutomationPolicy(
                workspace_id=UUID(workspace_id),
                revision=1,
                **values,
            )
        )
        await session.commit()


async def _create_product(
    workspace_id: str,
    *,
    title: str = "Eligible product",
    status: ProductStatus = ProductStatus.ACTIVE,
    affiliate_url: str | None = "https://affiliate.example/item",
    price: str = "10.00",
) -> UUID:
    # ``workspace_id`` is intentionally unused: the catalog is global. It is
    # accepted to make test call sites explicit about the owning request.
    del workspace_id
    async with SessionLocal() as session:
        product = Product(
            aliexpress_product_id=f"test-{uuid4().hex}",
            title=title,
            price=Decimal(price),
            discount=Decimal("10"),
            rating=Decimal("4.5"),
            sales=100,
            reviews=10,
            image_url="https://example.com/image.jpg",
            product_url="https://example.com/product",
            affiliate_url=affiliate_url,
            commission_rate=Decimal("5"),
            status=status,
        )
        session.add(product)
        await session.commit()
        await session.refresh(product)
        return product.id


async def _create_product_batch(workspace_id: str, marker: str, count: int) -> None:
    del workspace_id
    async with SessionLocal() as session:
        for index in range(count):
            session.add(
                Product(
                    aliexpress_product_id=f"{marker}-{index:04d}",
                    title=f"{marker} product {index}",
                    price=Decimal("10.00"),
                    discount=Decimal("10"),
                    rating=Decimal("4.5"),
                    sales=index,
                    reviews=10,
                    image_url="https://example.com/image.jpg",
                    product_url="https://example.com/product",
                    affiliate_url=f"https://affiliate.example/{marker}/{index}",
                    commission_rate=Decimal("5"),
                    status=ProductStatus.ACTIVE,
                )
            )
        await session.commit()


async def _create_queue_item(
    workspace_id: str,
    product_id: UUID,
    *,
    status: QueueStatus,
    published_at: datetime | None = None,
) -> UUID:
    async with SessionLocal() as session:
        item = QueueItem(
            workspace_id=UUID(workspace_id),
            product_id=product_id,
            content="test content",
            status=status,
            published_at=published_at,
        )
        session.add(item)
        await session.commit()
        await session.refresh(item)
        return item.id


async def _create_attempt(
    queue_id: UUID,
    *,
    number: int,
    status: str,
    occurred_at: datetime,
) -> None:
    async with SessionLocal() as session:
        attempt = QueuePublishAttempt(
            queue_id=queue_id,
            attempt_number=number,
            provider="facebook",
            status=status,
            content_hash=(f"{number:064x}")[-64:],
            idempotency_expires_at=occurred_at + timedelta(hours=1),
            occurred_at=occurred_at,
            error_code=None if status == "succeeded" else "test_error",
            error_message=None if status == "succeeded" else "test failure",
            provider_message_ref="post-ref" if status == "succeeded" else None,
        )
        session.add(attempt)
        await session.commit()


@pytest.mark.asyncio
async def test_preview_requires_authentication(client):
    response = await client.post(PREVIEW)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_preview_requires_a_saved_policy(client):
    _, token = await register_and_login(client)
    headers = await workspace_auth_headers(token)

    response = await client.post(PREVIEW, headers=headers)

    assert response.status_code == 404
    assert "policy" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_preview_is_workspace_scoped_and_read_only(client):
    _, token = await register_and_login(client)
    headers = await workspace_auth_headers(token)
    workspace_id = headers[WORKSPACE_ID_HEADER]
    product_id = await _create_product(workspace_id)
    await _create_policy(workspace_id, products_per_run=1)

    before = await _queue_count(workspace_id)
    response = await client.post(PREVIEW, headers=headers)
    after = await _queue_count(workspace_id)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["preview_only"] is True
    assert body["execution_available"] is False
    assert body["policy_enabled"] is False
    assert body["selected_products"][0]["product_id"] == str(product_id)
    assert before == after


@pytest.mark.asyncio
async def test_history_exclusions_do_not_cross_workspace_boundaries(client):
    _, token_a = await register_and_login(client)
    headers_a = await workspace_auth_headers(token_a)
    workspace_a = headers_a[WORKSPACE_ID_HEADER]
    marker = f"phase6b-isolation-{uuid4().hex[:8]}"
    product_id = await _create_product(workspace_a, title=f"{marker} shared catalog product")
    await _create_policy(workspace_a, keywords=marker, products_per_run=1)

    _, token_b = await register_and_login(client)
    headers_b = await workspace_auth_headers(token_b)
    workspace_b = headers_b[WORKSPACE_ID_HEADER]
    await _create_queue_item(workspace_b, product_id, status=QueueStatus.QUEUED)

    response = await client.post(PREVIEW, headers=headers_a)

    assert response.status_code == 200, response.text
    assert response.json()["selected_products"][0]["product_id"] == str(product_id)


@pytest.mark.asyncio
async def test_preview_excludes_inactive_missing_affiliate_and_workspace_history(client):
    _, token = await register_and_login(client)
    headers = await workspace_auth_headers(token)
    workspace_id = headers[WORKSPACE_ID_HEADER]
    await _create_policy(workspace_id, products_per_run=20)

    eligible_id = await _create_product(workspace_id, title="eligible phone case")
    inactive_id = await _create_product(
        workspace_id,
        status=ProductStatus.INACTIVE,
        title="inactive phone case",
    )
    missing_affiliate_id = await _create_product(
        workspace_id,
        affiliate_url="",
        title="missing phone case",
    )
    queued_id = await _create_product(workspace_id, title="queued phone case")
    await _create_queue_item(workspace_id, queued_id, status=QueueStatus.QUEUED)
    recent_id = await _create_product(workspace_id, title="recent phone case")
    await _create_queue_item(
        workspace_id,
        recent_id,
        status=QueueStatus.PUBLISHED,
        published_at=datetime.now(UTC) - timedelta(days=1),
    )
    ambiguous_id = await _create_product(workspace_id, title="ambiguous phone case")
    ambiguous_queue_id = await _create_queue_item(
        workspace_id,
        ambiguous_id,
        status=QueueStatus.FAILED,
    )
    await _create_attempt(
        ambiguous_queue_id,
        number=1,
        status="ambiguous",
        occurred_at=datetime.now(UTC) - timedelta(days=20),
    )
    resolved_id = await _create_product(workspace_id, title="resolved phone case")
    resolved_queue_id = await _create_queue_item(
        workspace_id,
        resolved_id,
        status=QueueStatus.FAILED,
    )
    resolved_at = datetime.now(UTC) - timedelta(days=20)
    await _create_attempt(
        resolved_queue_id,
        number=1,
        status="ambiguous",
        occurred_at=resolved_at,
    )
    await _create_attempt(
        resolved_queue_id,
        number=2,
        status="failed",
        occurred_at=resolved_at + timedelta(minutes=1),
    )

    response = await client.post(
        PREVIEW,
        headers=headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    selected_ids = {item["product_id"] for item in body["selected_products"]}
    assert str(eligible_id) in selected_ids
    assert str(resolved_id) in selected_ids
    assert str(inactive_id) not in selected_ids
    assert str(missing_affiliate_id) not in selected_ids
    assert str(queued_id) not in selected_ids
    assert str(recent_id) not in selected_ids
    assert str(ambiguous_id) not in selected_ids
    assert body["excluded_counts"]["queued_or_scheduled"] == 1
    assert body["excluded_counts"]["recently_published"] == 1
    assert body["excluded_counts"]["unresolved_ambiguous"] == 1
    # Products are global, so other tests/workspaces may contribute additional
    # invalid catalog rows to this bounded slice. The created row must be
    # counted, but the preview does not claim a workspace-global total.
    assert body["excluded_counts"]["missing_affiliate_url"] >= 1


@pytest.mark.asyncio
async def test_preview_applies_policy_boundaries_and_keywords(client):
    _, token = await register_and_login(client)
    headers = await workspace_auth_headers(token)
    workspace_id = headers[WORKSPACE_ID_HEADER]
    marker = f"phase6b-{uuid4().hex[:8]}"
    await _create_policy(
        workspace_id,
        keywords=f"{marker} phone case",
        min_price=Decimal("10.00"),
        max_price=Decimal("20.00"),
        min_commission=Decimal("5.00"),
        max_commission=Decimal("5.00"),
        products_per_run=10,
    )
    exact_id = await _create_product(
        workspace_id,
        title=f"{marker} Phone Case",
        price="10.00",
    )
    await _create_product(workspace_id, title=f"{marker} phone only", price="10.00")
    await _create_product(
        workspace_id,
        title=f"{marker} expensive phone case",
        price="20.01",
    )

    response = await client.post(PREVIEW, headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert [item["product_id"] for item in body["selected_products"]] == [str(exact_id)]
    assert body["eligible_count"] == 1
    assert body["selected_products"][0]["affiliate_url_present"] is True


@pytest.mark.asyncio
async def test_preview_marks_enabled_incomplete_policy_non_executable(client):
    _, token = await register_and_login(client)
    headers = await workspace_auth_headers(token)
    workspace_id = headers[WORKSPACE_ID_HEADER]
    await _create_policy(workspace_id, enabled=True, products_per_run=1)
    await _create_product(workspace_id)

    response = await client.post(PREVIEW, headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["policy_enabled"] is True
    assert body["configuration_ready"] is False
    assert body["execution_available"] is False
    assert body["preview_only"] is True
    assert any("not configuration-ready" in warning for warning in body["warnings"])


@pytest.mark.asyncio
async def test_preview_reports_candidate_cap_and_top_n(client):
    _, token = await register_and_login(client)
    headers = await workspace_auth_headers(token)
    workspace_id = headers[WORKSPACE_ID_HEADER]
    marker = f"cap-{uuid4().hex[:8]}"
    await _create_policy(workspace_id, keywords=marker, products_per_run=3)
    await _create_product_batch(workspace_id, marker, 1001)

    response = await client.post(PREVIEW, headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["truncated"] is True
    assert body["candidate_cap"] == 1000
    assert body["candidates_inspected"] == 1000
    assert body["ranking_scope"] == "inspected_candidates_only"
    assert body["selected_count"] == 3
    assert len(body["selected_products"]) == 3


async def _queue_count(workspace_id: str) -> int:
    async with SessionLocal() as session:
        result = await session.execute(
            select(QueueItem).where(QueueItem.workspace_id == UUID(workspace_id))
        )
        return len(result.scalars().all())
