"""Coverage for Telegram message/caption length splitting."""

import httpx
import pytest

from app.telegram.publisher import (
    TELEGRAM_MAX_CAPTION_LENGTH,
    TELEGRAM_MAX_MESSAGE_LENGTH,
    TelegramPublisher,
    split_telegram_text,
)
from app.telegram.types import InlineUrlButton


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload


def test_split_telegram_text_prefers_paragraph_boundaries():
    part_a = "A" * 100
    part_b = "B" * 100
    text = f"{part_a}\n\n{part_b}"
    chunks = split_telegram_text(text, 150)
    assert chunks == [part_a, part_b]
    assert all(len(chunk) <= 150 for chunk in chunks)
    assert "".join(chunks) == part_a + part_b


def test_split_telegram_text_hard_cuts_without_truncating():
    text = "x" * (TELEGRAM_MAX_MESSAGE_LENGTH + 50)
    chunks = split_telegram_text(text, TELEGRAM_MAX_MESSAGE_LENGTH)
    assert len(chunks) == 2
    assert len(chunks[0]) == TELEGRAM_MAX_MESSAGE_LENGTH
    assert len(chunks[1]) == 50
    assert "".join(chunks) == text


@pytest.mark.asyncio
async def test_publish_short_text_single_message(monkeypatch):
    posts: list[tuple[str, dict]] = []
    message_id = 10

    async def fake_post(self, url, json=None):
        nonlocal message_id
        method = url.rsplit("/", 1)[-1]
        posts.append((method, json or {}))
        message_id += 1
        return _FakeResponse(
            200,
            {"ok": True, "result": {"message_id": message_id, "chat": {"id": -100}}},
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    publisher = TelegramPublisher(bot_token="test-token")

    result = await publisher.publish("@channel", "Short post")

    assert result.message_id == 11
    assert result.message_type == "text"
    assert len(posts) == 1
    assert posts[0][0] == "sendMessage"
    assert posts[0][1]["text"] == "Short post"


@pytest.mark.asyncio
async def test_publish_long_text_sends_sequential_chunks(monkeypatch):
    posts: list[tuple[str, dict]] = []
    message_id = 0

    async def fake_post(self, url, json=None):
        nonlocal message_id
        method = url.rsplit("/", 1)[-1]
        posts.append((method, json or {}))
        message_id += 1
        return _FakeResponse(
            200,
            {"ok": True, "result": {"message_id": message_id, "chat": {"id": -100}}},
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    publisher = TelegramPublisher(bot_token="test-token")
    text = ("Paragraph one.\n\n" * 200) + ("Tail " * 200)
    assert len(text) > TELEGRAM_MAX_MESSAGE_LENGTH

    button = InlineUrlButton(text="Buy", url="https://example.com")
    result = await publisher.publish("@channel", text, button=button)

    assert result.message_id == 1
    assert len(posts) >= 2
    assert all(method == "sendMessage" for method, _ in posts)
    assert all(len(payload["text"]) <= TELEGRAM_MAX_MESSAGE_LENGTH for _, payload in posts)
    assert "reply_markup" not in posts[0][1]
    assert "reply_markup" in posts[-1][1]
    assert "".join(payload["text"] for _, payload in posts).replace("\n", "") == text.replace(
        "\n", ""
    )


@pytest.mark.asyncio
async def test_publish_long_photo_caption_splits_follow_up_text(monkeypatch):
    posts: list[tuple[str, dict]] = []
    message_id = 0

    async def fake_post(self, url, json=None):
        nonlocal message_id
        method = url.rsplit("/", 1)[-1]
        posts.append((method, json or {}))
        message_id += 1
        return _FakeResponse(
            200,
            {"ok": True, "result": {"message_id": message_id, "chat": {"id": -100}}},
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    publisher = TelegramPublisher(bot_token="test-token")
    text = ("Line of marketing copy.\n" * 80)
    assert len(text) > TELEGRAM_MAX_CAPTION_LENGTH

    result = await publisher.publish(
        "@channel",
        text,
        image_url="https://example.com/photo.jpg",
        button=InlineUrlButton(text="Shop", url="https://example.com/p"),
    )

    assert result.message_id == 1
    assert result.message_type == "photo"
    assert posts[0][0] == "sendPhoto"
    assert len(posts[0][1]["caption"]) <= TELEGRAM_MAX_CAPTION_LENGTH
    assert "reply_markup" not in posts[0][1]
    assert any(method == "sendMessage" for method, _ in posts[1:])
    assert "reply_markup" in posts[-1][1]
    for method, payload in posts[1:]:
        assert method == "sendMessage"
        assert len(payload["text"]) <= TELEGRAM_MAX_MESSAGE_LENGTH
