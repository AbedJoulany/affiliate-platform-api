"""Phase 1 Manual Telegram MVP: default channel, affiliate CTA, failed/retry."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.ai.product_context import ProductContext
from app.ai.prompts import build_marketing_prompt
from app.core.enums import QueueStatus
from app.models.product import Product
from app.models.workspace_settings import WorkspaceSettings
from app.repositories.queue import QueuePublishAttemptRepository, QueueRepository
from app.schemas.queue import QueueCreate, QueueUpdate
from app.services.exceptions import ConflictError, TelegramPublishError, ValidationError
from app.services.queue import (
    DEAD_LETTER_ERROR_CODE,
    QueueService,
    TelegramPublishingService,
    resolve_affiliate_cta_url,
)
from app.telegram.types import TelegramPublishResult
from tests.factories.queue_publishing import (
    create_publishable_channel,
    create_publishable_queue_item,
)


async def _settings(
    session,
    workspace_id,
    *,
    default_channel_id=None,
) -> WorkspaceSettings:
    row = WorkspaceSettings(
        workspace_id=workspace_id,
        default_telegram_channel_id=default_channel_id,
    )
    session.add(row)
    await session.flush()
    return row


async def _product(
    session,
    *,
    affiliate_url: str | None = "https://s.click.aliexpress.com/e/_promo",
    product_url: str = "https://www.aliexpress.com/item/100500.html",
) -> Product:
    product = Product(
        title="Affiliate gadget",
        price=Decimal("19.99"),
        image_url="https://example.com/gadget.png",
        product_url=product_url,
        affiliate_url=affiliate_url,
    )
    session.add(product)
    await session.flush()
    return product


@pytest.mark.asyncio
async def test_create_applies_workspace_default_channel(session):
    channel = await create_publishable_channel(session)
    await _settings(session, channel.workspace_id, default_channel_id=channel.id)

    item = await QueueService(session).create(
        QueueCreate(content="Needs a channel", status=QueueStatus.QUEUED),
        channel.workspace_id,
    )

    assert item.channel_id == channel.id


@pytest.mark.asyncio
async def test_explicit_channel_wins_over_workspace_default(session):
    default = await create_publishable_channel(session)
    explicit = await create_publishable_channel(session, workspace_id=default.workspace_id)
    await _settings(session, default.workspace_id, default_channel_id=default.id)

    item = await QueueService(session).create(
        QueueCreate(
            content="Explicit channel",
            status=QueueStatus.QUEUED,
            channel_id=explicit.id,
        ),
        default.workspace_id,
    )

    assert item.channel_id == explicit.id


@pytest.mark.asyncio
async def test_default_channel_from_another_workspace_is_rejected(session):
    local = await create_publishable_channel(session)
    foreign = await create_publishable_channel(session)
    await _settings(session, local.workspace_id, default_channel_id=foreign.id)

    with pytest.raises(ValidationError, match="invalid"):
        await QueueService(session).create(
            QueueCreate(content="Wrong workspace default", status=QueueStatus.QUEUED),
            local.workspace_id,
        )


@pytest.mark.asyncio
async def test_inactive_default_channel_is_rejected(session):
    channel = await create_publishable_channel(session, is_active=False)
    await _settings(session, channel.workspace_id, default_channel_id=channel.id)

    with pytest.raises(ValidationError, match="inactive"):
        await QueueService(session).create(
            QueueCreate(content="Inactive default", status=QueueStatus.QUEUED),
            channel.workspace_id,
        )


@pytest.mark.asyncio
async def test_queued_create_without_channel_or_default_is_rejected(session):
    channel = await create_publishable_channel(session)

    with pytest.raises(ValidationError, match="Telegram channel"):
        await QueueService(session).create(
            QueueCreate(content="Unpublishable", status=QueueStatus.QUEUED),
            channel.workspace_id,
        )


@pytest.mark.asyncio
async def test_draft_create_without_channel_remains_valid(session):
    channel = await create_publishable_channel(session)

    item = await QueueService(session).create(
        QueueCreate(content="Draft only"),
        channel.workspace_id,
    )

    assert item.channel_id is None
    assert item.status == QueueStatus.DRAFT


def test_resolve_affiliate_cta_prefers_explicit_button_url():
    assert (
        resolve_affiliate_cta_url(
            button_url="https://example.com/explicit",
            affiliate_url="https://s.click.aliexpress.com/e/_promo",
        )
        == "https://example.com/explicit"
    )


def test_resolve_affiliate_cta_uses_affiliate_url_when_button_missing():
    assert (
        resolve_affiliate_cta_url(
            button_url=None,
            affiliate_url="https://s.click.aliexpress.com/e/_promo",
        )
        == "https://s.click.aliexpress.com/e/_promo"
    )


def test_resolve_affiliate_cta_never_falls_back_to_product_url():
    assert resolve_affiliate_cta_url(button_url=None, affiliate_url=None) is None


@pytest.mark.asyncio
async def test_resolve_button_uses_affiliate_url_not_product_url(session):
    item = await create_publishable_queue_item(session, content="CTA")
    product = await _product(session)
    item.product = product
    item.button_url = None
    item.button_text = None

    button = TelegramPublishingService(session)._resolve_button(item)

    assert button is not None
    assert button.url == product.affiliate_url
    assert product.product_url not in button.url


@pytest.mark.asyncio
async def test_resolve_button_omits_cta_when_affiliate_url_missing(session):
    item = await create_publishable_queue_item(session, content="No CTA")
    product = await _product(session, affiliate_url=None)
    item.product = product
    item.button_url = None

    button = TelegramPublishingService(session)._resolve_button(item)

    assert button is None


@pytest.mark.asyncio
async def test_create_persists_affiliate_cta_from_product(session):
    channel = await create_publishable_channel(session)
    product = await _product(session)

    item = await QueueService(session).create(
        QueueCreate(
            content="From product",
            status=QueueStatus.QUEUED,
            channel_id=channel.id,
            product_id=product.id,
        ),
        channel.workspace_id,
    )

    assert item.button_url == product.affiliate_url
    assert item.button_text == "اشتري الآن"
    assert item.image_url == product.image_url
    assert item.button_url != product.product_url


def test_product_context_and_prompt_include_affiliate_url():
    product = Product(
        title="Prompt product",
        price=Decimal("5.00"),
        image_url="https://example.com/p.png",
        product_url="https://www.aliexpress.com/item/1.html",
        affiliate_url="https://s.click.aliexpress.com/e/_cta",
    )
    product.id = uuid4()
    context = ProductContext.from_product(product)
    prompt = build_marketing_prompt(context)

    assert context.affiliate_url == product.affiliate_url
    assert product.affiliate_url in prompt
    assert "رابط التسويق" in prompt
    assert product.product_url in prompt


def test_prompt_does_not_treat_product_url_as_marketing_cta():
    context = ProductContext(
        title="No affiliate",
        product_url="https://www.aliexpress.com/item/1.html",
    )
    prompt = build_marketing_prompt(context)

    assert "غير متوفر" in prompt
    assert "لا تستخدم رابط صفحة المنتج" in prompt


@pytest.mark.asyncio
async def test_terminal_failure_marks_queue_item_failed(
    session,
    mock_telegram_publisher_failure,
):
    item = await create_publishable_queue_item(session, content="Goes terminal")
    service = TelegramPublishingService(session)

    with pytest.raises(TelegramPublishError):
        await service.publish_queue_item(
            item.id,
            mark_transport_failure_terminal=True,
        )

    await session.refresh(item)
    assert item.status == QueueStatus.FAILED
    ready = await QueueRepository(session).list_queued_ready()
    assert item.id not in {row.id for row in ready}


@pytest.mark.asyncio
async def test_transient_failure_does_not_mark_item_failed(
    session,
    mock_telegram_publisher_failure,
):
    item = await create_publishable_queue_item(session, content="Retryable")
    service = TelegramPublishingService(session)

    with pytest.raises(TelegramPublishError):
        await service.publish_queue_item(item.id)

    await session.refresh(item)
    assert item.status == QueueStatus.QUEUED


@pytest.mark.asyncio
async def test_retry_failed_item_returns_to_queued_and_opens_new_attempt(
    session,
    monkeypatch,
):
    item = await create_publishable_queue_item(session, content="Retry me")
    calls = {"n": 0}

    async def fake_publish(self, chat_id, text, *, image_url=None, button=None, parse_mode=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TelegramPublishError("temporary", http_status=500)
        return TelegramPublishResult(
            chat_id=str(chat_id),
            message_id=9001,
            message_type="text",
        )

    monkeypatch.setattr("app.telegram.publisher.TelegramPublisher.publish", fake_publish)
    publisher = TelegramPublishingService(session)
    with pytest.raises(TelegramPublishError):
        await publisher.publish_queue_item(item.id, mark_transport_failure_terminal=True)

    await session.refresh(item)
    assert item.status == QueueStatus.FAILED

    queue = QueueService(session)
    retried = await queue.update(
        item.id,
        QueueUpdate(status=QueueStatus.QUEUED),
        item.workspace_id,
    )
    assert retried.status == QueueStatus.QUEUED

    response = await queue.publish(item.id, item.workspace_id)
    assert response.telegram_message_id == 9001

    latest = await QueuePublishAttemptRepository(session).latest_attempt(item.id)
    assert latest is not None
    assert latest.attempt_number == 2
    assert latest.status == "succeeded"
    await session.refresh(item)
    assert item.status == QueueStatus.PUBLISHED


@pytest.mark.asyncio
async def test_retry_failed_scheduled_item_keeps_future_schedule(session):
    item = await create_publishable_queue_item(
        session,
        content="Later",
        status=QueueStatus.SCHEDULED,
    )
    item.scheduled_at = datetime.now(UTC) + timedelta(hours=2)
    item.status = QueueStatus.FAILED
    await session.flush()

    updated = await QueueService(session).update(
        item.id,
        QueueUpdate(status=QueueStatus.SCHEDULED, scheduled_at=item.scheduled_at),
        item.workspace_id,
    )

    assert updated.status == QueueStatus.SCHEDULED
    assert updated.scheduled_at is not None
    due = await QueueRepository(session).list_scheduled_due(
        due_before=datetime.now(UTC),
        limit=50,
    )
    assert item.id not in {row.id for row in due}


@pytest.mark.asyncio
async def test_idempotency_still_blocks_duplicate_success(
    session,
    mock_telegram_publisher_success,
):
    item = await create_publishable_queue_item(session, content="Once only")
    service = TelegramPublishingService(session)
    await service.publish_queue_item(item.id)

    with pytest.raises(ConflictError, match="already completed"):
        await service.publish_queue_item(item.id)

    latest = await QueuePublishAttemptRepository(session).latest_attempt(item.id)
    assert latest is not None
    assert latest.attempt_number == 1
    assert latest.error_code != DEAD_LETTER_ERROR_CODE
