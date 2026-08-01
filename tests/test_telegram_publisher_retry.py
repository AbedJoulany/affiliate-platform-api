"""MVP Telegram retry and terminal dead-letter coverage."""

import httpx
import pytest

from app.core.enums import QueueStatus
from app.repositories.queue import QueuePublishAttemptRepository
from app.services.exceptions import TelegramPublishError
from app.services.queue import DEAD_LETTER_ERROR_CODE, TelegramPublishingService
from app.telegram.publisher import TELEGRAM_BASE_BACKOFF_SECONDS, TelegramPublisher
from tests.factories.queue_publishing import create_publishable_queue_item


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload


@pytest.mark.asyncio
async def test_http_429_honors_retry_after(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.telegram.publisher.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("app.telegram.publisher.random.uniform", lambda a, b: 0.0)

    queue = [
        _FakeResponse(
            429,
            {
                "ok": False,
                "error_code": 429,
                "description": "Too Many Requests",
                "parameters": {"retry_after": 7},
            },
        ),
        _FakeResponse(
            200,
            {
                "ok": True,
                "result": {
                    "message_id": 42,
                    "chat": {"id": -1001},
                },
            },
        ),
    ]
    post_calls: list[object] = []

    async def fake_post(self, url, json=None):
        post_calls.append(json)
        return queue.pop(0)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    publisher = TelegramPublisher(bot_token="test-token")
    result = await publisher.send_text("@channel", "rate limited then ok")

    assert result.message_id == 42
    assert len(post_calls) == 2
    assert len(sleeps) == 1
    # retry_after=7 with jitter patched to 0 — not plain exponential backoff (0.5).
    assert sleeps[0] == 7.0
    assert sleeps[0] > TELEGRAM_BASE_BACKOFF_SECONDS


@pytest.mark.asyncio
async def test_non_retryable_4xx_raises_immediately(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.telegram.publisher.asyncio.sleep", fake_sleep)
    post_calls: list[object] = []

    async def fake_post(self, url, json=None):
        post_calls.append(json)
        return _FakeResponse(
            400,
            {
                "ok": False,
                "error_code": 400,
                "description": "Bad Request: chat not found",
            },
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    publisher = TelegramPublisher(bot_token="test-token")
    with pytest.raises(TelegramPublishError, match="chat not found"):
        await publisher.send_text("@missing", "no retry")

    assert len(post_calls) == 1
    assert sleeps == []


@pytest.mark.asyncio
async def test_terminal_transport_failure_marks_dead_letter(
    session,
    mock_telegram_publisher_failure,
):
    item = await create_publishable_queue_item(session, content="Terminal transport")
    original_status = item.status
    service = TelegramPublishingService(session)

    with pytest.raises(TelegramPublishError):
        await service.publish_queue_item(
            item.id,
            mark_transport_failure_terminal=True,
        )

    await session.refresh(item)
    assert item.status == original_status
    assert item.status in {
        QueueStatus.DRAFT,
        QueueStatus.QUEUED,
        QueueStatus.SCHEDULED,
        QueueStatus.PUBLISHED,
    }

    latest = await QueuePublishAttemptRepository(session).latest_attempt(item.id)
    assert latest is not None
    assert latest.status == "failed"
    assert latest.error_code == DEAD_LETTER_ERROR_CODE
