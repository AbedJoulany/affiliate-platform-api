from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select

from app.core.enums import BotPermissionStatus, ProductStatus, QueueStatus
from app.core.workspace import WORKSPACE_ID_HEADER
from app.models.automation_policy import AutomationPolicy
from app.models.channel import TelegramChannel
from app.models.product import Product
from app.models.queue import QueueItem
from app.schemas.automation_content import (
    AutomationContentPreviewResponse,
    AutomationContentProductResult,
)
from app.services.automation_scheduling import (
    candidate_schedule_slots,
    local_date_range_utc_bounds,
    select_schedule_slots,
)
from tests.conftest import SessionLocal
from tests.test_api_endpoints import API_PREFIX, register_and_login, workspace_auth_headers

PREPARE = f"{API_PREFIX}/automation/queue/prepare"


@pytest.mark.parametrize(
    ("local_day", "expected_hours"),
    [
        (date(2026, 3, 8), 23),
        (date(2026, 11, 1), 25),
    ],
)
def test_local_day_utc_bounds_follow_dst_length(local_day, expected_hours):
    start_utc, end_utc = local_date_range_utc_bounds(
        local_day,
        local_day,
        "America/New_York",
    )

    assert (end_utc - start_utc) == timedelta(hours=expected_hours)


@pytest.fixture(autouse=True)
async def cleanup_automation_queue_products():
    async with SessionLocal() as session:
        await session.execute(
            delete(Product).where(Product.aliexpress_product_id.like("automation-%"))
        )
        await session.commit()
    yield
    async with SessionLocal() as session:
        await session.execute(
            delete(Product).where(Product.aliexpress_product_id.like("automation-%"))
        )
        await session.commit()


def test_schedule_candidates_are_future_and_deterministic():
    now = datetime(2026, 11, 21, 8, 0, tzinfo=UTC)
    slots = candidate_schedule_slots(
        now_utc=now,
        timezone_name="UTC",
        preferred_time_local=time(9, 0),
        posts_per_day=2,
    )

    assert slots[0].scheduled_at == datetime(2026, 11, 21, 9, 0, tzinfo=UTC)
    assert slots[1].scheduled_at == datetime(2026, 11, 21, 21, 0, tzinfo=UTC)
    assert all(slot.scheduled_at > now for slot in slots)


def test_schedule_resolution_handles_dst_gap_and_fold():
    gap = candidate_schedule_slots(
        now_utc=datetime(2026, 3, 8, 0, 0, tzinfo=UTC),
        timezone_name="America/New_York",
        preferred_time_local=time(2, 30),
        posts_per_day=1,
    )[0]
    fold = candidate_schedule_slots(
        now_utc=datetime(2026, 11, 1, 0, 0, tzinfo=UTC),
        timezone_name="America/New_York",
        preferred_time_local=time(1, 30),
        posts_per_day=1,
    )[0]

    # 02:30 does not exist; the first valid wall-clock minute is 03:00.
    assert gap.scheduled_at == datetime(2026, 3, 8, 7, 0, tzinfo=UTC)
    # The first occurrence of the fall-back hour is selected (fold=0).
    assert fold.scheduled_at == datetime(2026, 11, 1, 5, 30, tzinfo=UTC)


def test_schedule_selection_counts_existing_items_in_workspace_local_day():
    now = datetime(2026, 11, 21, 8, 0, tzinfo=UTC)
    candidates = candidate_schedule_slots(
        now_utc=now,
        timezone_name="Asia/Jerusalem",
        preferred_time_local=time(12, 0),
        posts_per_day=1,
    )
    selected = select_schedule_slots(
        candidates=candidates,
        existing_timestamps=[candidates[0].scheduled_at],
        timezone_name="Asia/Jerusalem",
        daily_limit=1,
        count=1,
    )

    assert selected[0].local_date > candidates[0].local_date


@pytest.mark.asyncio
async def test_prepare_creates_scheduled_queue_item_with_canonical_affiliate_url(
    client,
    monkeypatch,
):
    _, token = await register_and_login(client, role="user")
    headers = await workspace_auth_headers(token)
    workspace_id = UUID(headers[WORKSPACE_ID_HEADER])
    channel_id = uuid4()
    product_id = uuid4()

    async with SessionLocal() as session:
        session.add(
            TelegramChannel(
                id=channel_id,
                workspace_id=workspace_id,
                telegram_channel_id=f"automation-{uuid4().hex}",
                title="Automation channel",
                is_active=True,
                bot_permission_status=BotPermissionStatus.GRANTED,
                can_post_messages=True,
                can_edit_messages=True,
                can_delete_messages=True,
            )
        )
        session.add(
            Product(
                id=product_id,
                aliexpress_product_id=f"automation-{uuid4().hex}",
                title="Automation product",
                price=Decimal("10.00"),
                discount=Decimal("10"),
                rating=Decimal("4.5"),
                sales=100,
                reviews=10,
                image_url="https://example.com/image.jpg",
                product_url="https://example.com/product",
                affiliate_url="https://affiliate.example/canonical",
                commission_rate=Decimal("5"),
                status=ProductStatus.ACTIVE,
            )
        )
        session.add(
            AutomationPolicy(
                workspace_id=workspace_id,
                revision=1,
                provider="telegram",
                telegram_channel_id=channel_id,
                posts_per_day=1,
                preferred_time_local=time(23, 0),
            )
        )
        await session.commit()

    async def fake_preview(self, user, workspace_id, payload, *, authorize_policy=True):
        del self, user, payload, authorize_policy
        return AutomationContentPreviewResponse(
            workspace_id=workspace_id,
            policy_id=uuid4(),
            policy_revision=1,
            generated_at=datetime.now(UTC),
            requested_max_products=1,
            selected_count=1,
            generated_count=1,
            failed_count=0,
            provider="openai",
            results=[
                AutomationContentProductResult(
                    product_id=product_id,
                    selection_rank=1,
                    recommendation_score=80.0,
                    status="generated",
                    content="محتوى آمن",
                    affiliate_url="https://affiliate.example/canonical",
                )
            ],
        )

    monkeypatch.setattr(
        "app.services.automation_queue.AutomationContentGenerationService.preview",
        fake_preview,
    )
    response = await client.post(
        PREPARE,
        headers=headers,
        json={
            "expected_policy_revision": 1,
            "max_products": 1,
            "acknowledge_ai_cost": True,
            "confirm_scheduled_publishing": True,
            "idempotency_key": "automation-test-1",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["scheduled_count"] == 1
    assert body["results"][0]["status"] == "scheduled"
    assert "may be published automatically" in body["warnings"][-1]

    async with SessionLocal() as session:
        result = await session.execute(
            select(QueueItem).where(
                QueueItem.workspace_id == workspace_id,
                QueueItem.product_id == product_id,
            )
        )
        item = result.scalar_one()
        assert item.status == QueueStatus.SCHEDULED
        assert item.button_url == "https://affiliate.example/canonical"
        assert item.button_url != "https://example.com/product"
        assert item.scheduled_at is not None
        assert item.scheduled_at > datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=5)


@pytest.mark.asyncio
async def test_prepare_fails_closed_without_a_ready_destination(client, monkeypatch):
    _, token = await register_and_login(client, role="user")
    headers = await workspace_auth_headers(token)
    workspace_id = UUID(headers[WORKSPACE_ID_HEADER])

    async with SessionLocal() as session:
        session.add(
            AutomationPolicy(
                workspace_id=workspace_id,
                revision=1,
                provider="telegram",
                telegram_channel_id=None,
            )
        )
        await session.commit()

    async def should_not_generate(*args, **kwargs):
        raise AssertionError("AI generation must not start without a ready destination")

    monkeypatch.setattr(
        "app.services.automation_queue.AutomationContentGenerationService.preview",
        should_not_generate,
    )
    response = await client.post(
        PREPARE,
        headers=headers,
        json={
            "expected_policy_revision": 1,
            "acknowledge_ai_cost": True,
            "confirm_scheduled_publishing": True,
            "idempotency_key": "no-destination-1",
        },
    )

    assert response.status_code == 422
    assert "telegram channel" in response.json()["detail"].lower()
