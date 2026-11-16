"""Backend-only Facebook Queue publishing tests with mocked provider calls."""

import base64
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
import pytest

from app.core.config import get_settings
from app.core.enums import FacebookPageValidationStatus, QueueStatus
from app.facebook.client import FacebookGraphClient, FacebookGraphError
from app.facebook.crypto import FacebookTokenCipher
from app.facebook.publisher import FacebookPublisher, FacebookPublishResult
from app.models.facebook_page import FacebookPage
from app.models.queue import QueueItem, QueuePublishAttempt
from app.repositories.queue import QueuePublishAttemptRepository
from app.services.exceptions import ConflictError, FacebookPublishError
from app.services.queue import TelegramPublishingService


def _key() -> str:
    return base64.urlsafe_b64encode(b"facebook-queue-test-key-32bytes!").decode()


@pytest.mark.asyncio
async def test_facebook_text_publishing_preserves_affiliate_url(monkeypatch, session):
    settings = get_settings()
    monkeypatch.setattr(settings, "facebook_token_encryption_key", _key())
    workspace_id = uuid4()
    page = FacebookPage(
        workspace_id=workspace_id,
        facebook_page_id="123456",
        page_name="Test Page",
        encrypted_access_token=FacebookTokenCipher(_key()).encrypt("test-token"),
        validation_status=FacebookPageValidationStatus.VALID,
        last_validated_at=datetime.now(UTC),
    )
    session.add(page)
    await session.flush()
    item = QueueItem(
        workspace_id=workspace_id,
        provider="facebook",
        facebook_page_id=page.id,
        content="Buy this item",
        button_url="https://affiliate.example/offer",
        status=QueueStatus.QUEUED,
    )
    session.add(item)
    await session.flush()

    calls: list[dict] = []

    async def fake_publish(
        self, page_id, access_token, text, *, image_url=None, affiliate_url=None
    ):
        calls.append(
            {
                "page_id": page_id,
                "token": access_token,
                "text": text,
                "image_url": image_url,
                "affiliate_url": affiliate_url,
            }
        )
        return FacebookPublishResult(page_id, "123456_789", "text")

    monkeypatch.setattr("app.facebook.publisher.FacebookPublisher.publish", fake_publish)

    result = await TelegramPublishingService(session).publish_queue_item(item.id)

    assert result.provider == "facebook"
    assert result.provider_message_ref == "123456_789"
    assert calls[0]["affiliate_url"] == "https://affiliate.example/offer"
    assert calls[0]["token"] == "test-token"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "expires_at",
    [
        pytest.param(datetime.now(UTC) + timedelta(hours=1), id="within-window"),
        pytest.param(datetime.now(UTC) - timedelta(hours=1), id="after-window"),
    ],
)
async def test_published_facebook_item_cannot_create_a_republish_attempt(
    monkeypatch, session, expires_at
):
    settings = get_settings()
    monkeypatch.setattr(settings, "facebook_token_encryption_key", _key())
    workspace_id = uuid4()
    page = FacebookPage(
        workspace_id=workspace_id,
        facebook_page_id="1234560",
        page_name="Test Page",
        encrypted_access_token=FacebookTokenCipher(_key()).encrypt("test-token"),
        validation_status=FacebookPageValidationStatus.VALID,
    )
    session.add(page)
    await session.flush()
    item = QueueItem(
        workspace_id=workspace_id,
        provider="facebook",
        facebook_page_id=page.id,
        content="Already published",
        status=QueueStatus.PUBLISHED,
        published_at=datetime.now(UTC),
    )
    session.add(item)
    await session.flush()
    item.facebook_page = page
    service = TelegramPublishingService(session)
    snapshot = service._build_publish_snapshot(item)
    repository = QueuePublishAttemptRepository(session)
    original_attempt = await repository.create_attempt(
        QueuePublishAttempt(
            queue_id=item.id,
            attempt_number=1,
            provider="facebook",
            status="succeeded",
            content_hash=snapshot.content_hash,
            idempotency_expires_at=expires_at,
            occurred_at=datetime.now(UTC),
            provider_message_ref="1234560_789",
        )
    )
    calls: list[bool] = []

    async def should_not_publish(*args, **kwargs):
        calls.append(True)
        raise AssertionError("published Queue items must not reach the provider")

    monkeypatch.setattr("app.facebook.publisher.FacebookPublisher.publish", should_not_publish)

    with pytest.raises(ConflictError, match="already completed"):
        await service.publish_queue_item(item.id)

    await session.refresh(item)
    attempts = await repository.list_attempts(item.id)
    assert item.status == QueueStatus.PUBLISHED
    assert len(attempts) == 1
    assert attempts[0].id == original_attempt.id
    assert attempts[0].status == "succeeded"
    assert attempts[0].provider_message_ref == "1234560_789"
    assert calls == []


@pytest.mark.asyncio
async def test_ambiguous_facebook_delivery_blocks_ordinary_retry(monkeypatch, session):
    settings = get_settings()
    monkeypatch.setattr(settings, "facebook_token_encryption_key", _key())
    workspace_id = uuid4()
    page = FacebookPage(
        workspace_id=workspace_id,
        facebook_page_id="123457",
        page_name="Test Page",
        encrypted_access_token=FacebookTokenCipher(_key()).encrypt("test-token"),
        validation_status=FacebookPageValidationStatus.VALID,
    )
    session.add(page)
    await session.flush()
    item = QueueItem(
        workspace_id=workspace_id,
        provider="facebook",
        facebook_page_id=page.id,
        content="Possibly delivered",
        status=QueueStatus.QUEUED,
    )
    session.add(item)
    await session.flush()

    async def ambiguous_publish(*args, **kwargs):
        raise FacebookPublishError("transport uncertain", http_status=504, ambiguous=True)

    monkeypatch.setattr("app.facebook.publisher.FacebookPublisher.publish", ambiguous_publish)
    service = TelegramPublishingService(session)

    with pytest.raises(FacebookPublishError):
        await service.publish_queue_item(item.id)
    await session.refresh(item)
    assert item.status == QueueStatus.FAILED
    attempt = await QueuePublishAttemptRepository(session).latest_attempt(item.id)
    assert attempt is not None
    assert attempt.status == "ambiguous"

    with pytest.raises(ConflictError, match="delivery is uncertain"):
        await service.publish_queue_item(item.id)


@pytest.mark.asyncio
async def test_confirmed_ambiguous_facebook_retry_creates_new_successful_attempt(
    monkeypatch, session
):
    settings = get_settings()
    monkeypatch.setattr(settings, "facebook_token_encryption_key", _key())
    workspace_id = uuid4()
    page = FacebookPage(
        workspace_id=workspace_id,
        facebook_page_id="123460",
        page_name="Test Page",
        encrypted_access_token=FacebookTokenCipher(_key()).encrypt("test-token"),
        validation_status=FacebookPageValidationStatus.VALID,
    )
    session.add(page)
    await session.flush()
    item = QueueItem(
        workspace_id=workspace_id,
        provider="facebook",
        facebook_page_id=page.id,
        content="Retry after operator confirmation",
        status=QueueStatus.FAILED,
    )
    session.add(item)
    await session.flush()
    item.facebook_page = page
    repository = QueuePublishAttemptRepository(session)
    snapshot = TelegramPublishingService(session)._build_publish_snapshot(item)
    await repository.create_attempt(
        QueuePublishAttempt(
            queue_id=item.id,
            attempt_number=1,
            provider="facebook",
            status="ambiguous",
            error_code="facebook_ambiguous_delivery",
            error_message="Delivery status is uncertain",
            content_hash=snapshot.content_hash,
            idempotency_expires_at=datetime.now(UTC),
            occurred_at=datetime.now(UTC),
        )
    )

    async def confirmed_publish(*args, **kwargs):
        return FacebookPublishResult("123460", "123460_999", "text")

    monkeypatch.setattr(
        "app.facebook.publisher.FacebookPublisher.publish", confirmed_publish
    )

    result = await TelegramPublishingService(session).publish_queue_item(
        item.id, allow_ambiguous=True
    )

    assert result.provider_message_ref == "123460_999"
    await session.refresh(item)
    assert item.status == QueueStatus.PUBLISHED
    attempts = await repository.list_attempts(item.id)
    assert {attempt.attempt_number for attempt in attempts} == {1, 2}
    assert next(attempt for attempt in attempts if attempt.attempt_number == 2).status == (
        "succeeded"
    )


@pytest.mark.asyncio
async def test_expired_started_facebook_attempt_stays_blocked(session):
    workspace_id = uuid4()
    page = FacebookPage(
        workspace_id=workspace_id,
        facebook_page_id="123458",
        page_name="Test Page",
        encrypted_access_token="v1.test.envelope",
        validation_status=FacebookPageValidationStatus.VALID,
    )
    session.add(page)
    await session.flush()
    item = QueueItem(
        workspace_id=workspace_id,
        provider="facebook",
        facebook_page_id=page.id,
        content="Uncertain after worker crash",
        status=QueueStatus.QUEUED,
    )
    session.add(item)
    await session.flush()
    attempt = await QueuePublishAttemptRepository(session).create_attempt(
        QueuePublishAttempt(
            queue_id=item.id,
            attempt_number=1,
            provider="facebook",
            status="started",
            content_hash="a" * 64,
            idempotency_expires_at=datetime.now(UTC),
            occurred_at=datetime.now(UTC),
        )
    )
    assert attempt.status == "started"

    with pytest.raises(ConflictError, match="delivery is uncertain"):
        await TelegramPublishingService(session).publish_queue_item(item.id)


@pytest.mark.asyncio
async def test_active_facebook_attempt_cannot_be_bypassed_by_confirmation(session):
    workspace_id = uuid4()
    page = FacebookPage(
        workspace_id=workspace_id,
        facebook_page_id="123459",
        page_name="Test Page",
        encrypted_access_token="v1.test.envelope",
        validation_status=FacebookPageValidationStatus.VALID,
    )
    session.add(page)
    await session.flush()
    item = QueueItem(
        workspace_id=workspace_id,
        provider="facebook",
        facebook_page_id=page.id,
        content="Still in flight",
        status=QueueStatus.QUEUED,
    )
    session.add(item)
    await session.flush()
    item.facebook_page = page
    service = TelegramPublishingService(session)
    snapshot = service._build_publish_snapshot(item)
    await QueuePublishAttemptRepository(session).create_attempt(
        QueuePublishAttempt(
            queue_id=item.id,
            attempt_number=1,
            provider="facebook",
            status="started",
            content_hash=snapshot.content_hash,
            idempotency_expires_at=datetime.now(UTC).replace(year=2099),
            occurred_at=datetime.now(UTC),
        )
    )

    with pytest.raises(ConflictError, match="in progress"):
        await service.publish_queue_item(item.id, allow_ambiguous=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [429, 401, 403])
async def test_scheduled_facebook_provider_errors_are_terminal_and_not_reselected(
    monkeypatch, session, status_code
):
    settings = get_settings()
    monkeypatch.setattr(settings, "facebook_token_encryption_key", _key())
    workspace_id = uuid4()
    page = FacebookPage(
        workspace_id=workspace_id,
        facebook_page_id="1234561",
        page_name="Test Page",
        encrypted_access_token=FacebookTokenCipher(_key()).encrypt("test-token"),
        validation_status=FacebookPageValidationStatus.VALID,
    )
    session.add(page)
    await session.flush()
    item = QueueItem(
        workspace_id=workspace_id,
        provider="facebook",
        facebook_page_id=page.id,
        content="Rate limited scheduled post",
        status=QueueStatus.SCHEDULED,
        scheduled_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    session.add(item)
    await session.flush()
    calls: list[bool] = []

    async def rate_limited(*args, **kwargs):
        calls.append(True)
        raise FacebookPublishError("Facebook provider error", http_status=status_code)

    monkeypatch.setattr("app.facebook.publisher.FacebookPublisher.publish", rate_limited)
    service = TelegramPublishingService(session)

    assert await service.publish_due_scheduled(limit=1) == []
    await session.refresh(item)
    attempt = await QueuePublishAttemptRepository(session).latest_attempt(item.id)
    assert item.status == QueueStatus.FAILED
    assert attempt is not None
    assert attempt.status == "failed"
    assert attempt.error_code == f"facebook_{status_code}"
    assert calls == [True]

    assert await service.publish_due_scheduled(limit=1) == []
    assert calls == [True]


@pytest.mark.asyncio
async def test_scheduled_facebook_success_is_persisted_once(monkeypatch, session):
    settings = get_settings()
    monkeypatch.setattr(settings, "facebook_token_encryption_key", _key())
    workspace_id = uuid4()
    page = FacebookPage(
        workspace_id=workspace_id,
        facebook_page_id="1234562",
        page_name="Test Page",
        encrypted_access_token=FacebookTokenCipher(_key()).encrypt("test-token"),
        validation_status=FacebookPageValidationStatus.VALID,
    )
    session.add(page)
    await session.flush()
    item = QueueItem(
        workspace_id=workspace_id,
        provider="facebook",
        facebook_page_id=page.id,
        content="Scheduled Facebook post",
        status=QueueStatus.SCHEDULED,
        scheduled_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    session.add(item)
    await session.flush()
    calls: list[bool] = []

    async def publish_once(*args, **kwargs):
        calls.append(True)
        return FacebookPublishResult("1234562", "1234562_789", "text")

    monkeypatch.setattr("app.facebook.publisher.FacebookPublisher.publish", publish_once)
    service = TelegramPublishingService(session)

    results = await service.publish_due_scheduled(limit=1)
    assert len(results) == 1
    await session.refresh(item)
    attempts = await QueuePublishAttemptRepository(session).list_attempts(item.id)
    assert item.status == QueueStatus.PUBLISHED
    assert len(attempts) == 1
    assert attempts[0].status == "succeeded"
    assert attempts[0].provider_message_ref == "1234562_789"
    assert calls == [True]

    assert await service.publish_due_scheduled(limit=1) == []
    assert calls == [True]


@pytest.mark.asyncio
async def test_graph_publish_token_is_not_in_url():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"post_id": "123_456"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await FacebookGraphClient(http_client=client).publish_feed(
            "123",
            "test-token",
            message="hello",
            link="https://affiliate.example/offer",
        )

    assert result == "123_456"
    assert "test-token" not in str(requests[0].url)
    assert requests[0].headers["authorization"].startswith("Bearer ")


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [401, 403])
async def test_graph_publish_permission_errors_are_sanitized(status_code):
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(status_code, json={"error": {"message": "secret provider detail"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FacebookGraphError) as exc_info:
            await FacebookGraphClient(http_client=client).publish_feed(
                "123",
                "test-token",
                message="hello",
            )

    assert exc_info.value.status_code == 422
    assert str(exc_info.value) == "Facebook credentials lack publishing access"
    assert "secret provider detail" not in str(exc_info.value)
    assert "test-token" not in str(requests[0].url)


@pytest.mark.asyncio
async def test_photo_caption_contains_affiliate_url():
    class FakeClient:
        async def publish_photo(self, *args, **kwargs):
            assert kwargs["caption"].endswith("https://affiliate.example/offer")
            return "123_789"

    result = await FacebookPublisher(FakeClient()).publish(
        "123",
        "test-token",
        "Image caption",
        image_url="https://example.com/image.jpg",
        affiliate_url="https://affiliate.example/offer",
    )
    assert result.post_id == "123_789"
