import asyncio
import json
import random

import httpx

from app.core.config import get_settings
from app.services.exceptions import TelegramPublishError, ValidationError
from app.telegram.types import InlineUrlButton, TelegramPublishResult

settings = get_settings()

# Retry policy: 1 initial attempt + up to 3 retries = at most 4 HTTP attempts.
# Celery tasks use the same "3 retries" meaning via max_retries=3.
TELEGRAM_MAX_RETRIES = 3
TELEGRAM_BASE_BACKOFF_SECONDS = 0.5
TELEGRAM_JITTER_SECONDS = 0.25

# Official Bot API limits (characters after entities parsing).
TELEGRAM_MAX_MESSAGE_LENGTH = 4096
TELEGRAM_MAX_CAPTION_LENGTH = 1024


def _telegram_cut_index(text: str, max_length: int) -> int:
    """Return an end index for the next chunk, preferring soft boundaries."""
    if len(text) <= max_length:
        return len(text)
    window = text[:max_length]
    min_soft = max_length // 2
    for separator in ("\n\n", "\n", " "):
        index = window.rfind(separator)
        if index >= min_soft:
            return index
    return max_length


def split_telegram_text(text: str, max_length: int) -> list[str]:
    """Split ``text`` into chunks that fit Telegram length limits.

    Prefers paragraph (``\\n\\n``), then line, then word boundaries so formatting
    and readability are preserved when possible. Never truncates content.
    """
    if max_length < 1:
        raise ValueError("max_length must be positive")
    if not text:
        return [""]
    if len(text) <= max_length:
        return [text]

    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break
        cut = _telegram_cut_index(remaining, max_length)
        chunk = remaining[:cut].rstrip("\n")
        if not chunk:
            chunk = remaining[:max_length]
            cut = len(chunk)
        chunks.append(chunk)
        remaining = remaining[cut:].lstrip("\n")
    return chunks


class TelegramPublisher:
    def __init__(self, bot_token: str | None = None) -> None:
        self.bot_token = bot_token or settings.telegram_bot_token
        self.base_url = settings.telegram_api_base_url.rstrip("/")

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token)

    def _ensure_configured(self) -> None:
        if not self.is_configured:
            raise ValidationError("Telegram bot token is not configured")

    async def send_text(
        self,
        chat_id: str,
        text: str,
        *,
        button: InlineUrlButton | None = None,
        parse_mode: str | None = None,
    ) -> TelegramPublishResult:
        self._ensure_configured()
        payload: dict = {
            "chat_id": chat_id,
            "text": text,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if button:
            payload["reply_markup"] = self._build_inline_keyboard(button)

        data = await self._post("sendMessage", payload)
        message = data["result"]
        return TelegramPublishResult(
            chat_id=str(message["chat"]["id"]),
            message_id=message["message_id"],
            message_type="text",
        )

    async def send_photo(
        self,
        chat_id: str,
        photo_url: str,
        *,
        caption: str | None = None,
        button: InlineUrlButton | None = None,
        parse_mode: str | None = None,
    ) -> TelegramPublishResult:
        self._ensure_configured()
        payload: dict = {
            "chat_id": chat_id,
            "photo": photo_url,
        }
        if caption:
            payload["caption"] = caption
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if button:
            payload["reply_markup"] = self._build_inline_keyboard(button)

        data = await self._post("sendPhoto", payload)
        message = data["result"]
        return TelegramPublishResult(
            chat_id=str(message["chat"]["id"]),
            message_id=message["message_id"],
            message_type="photo",
        )

    async def publish(
        self,
        chat_id: str,
        text: str,
        *,
        image_url: str | None = None,
        button: InlineUrlButton | None = None,
        parse_mode: str | None = None,
    ) -> TelegramPublishResult:
        """Publish text (and optional photo), splitting when over Telegram limits.

        ``provider_message_id`` / ``message_id`` always refers to the first
        outbound message (the photo, or the first text chunk). Follow-up chunks
        are sent sequentially afterward. The inline button is attached only to
        the final message so it stays with the end of the post.
        """
        if image_url:
            return await self._publish_with_photo(
                chat_id,
                text,
                image_url=image_url,
                button=button,
                parse_mode=parse_mode,
            )
        return await self._publish_text_chunks(
            chat_id,
            text,
            button=button,
            parse_mode=parse_mode,
        )

    async def _publish_text_chunks(
        self,
        chat_id: str,
        text: str,
        *,
        button: InlineUrlButton | None,
        parse_mode: str | None,
    ) -> TelegramPublishResult:
        chunks = split_telegram_text(text, TELEGRAM_MAX_MESSAGE_LENGTH)
        primary: TelegramPublishResult | None = None
        for index, chunk in enumerate(chunks):
            is_last = index == len(chunks) - 1
            result = await self.send_text(
                chat_id,
                chunk,
                button=button if is_last else None,
                parse_mode=parse_mode,
            )
            if primary is None:
                primary = result
        assert primary is not None
        return primary

    async def _publish_with_photo(
        self,
        chat_id: str,
        text: str,
        *,
        image_url: str,
        button: InlineUrlButton | None,
        parse_mode: str | None,
    ) -> TelegramPublishResult:
        if len(text) <= TELEGRAM_MAX_CAPTION_LENGTH:
            return await self.send_photo(
                chat_id,
                image_url,
                caption=text or None,
                button=button,
                parse_mode=parse_mode,
            )

        cut = _telegram_cut_index(text, TELEGRAM_MAX_CAPTION_LENGTH)
        caption = text[:cut].rstrip("\n")
        if not caption:
            caption = text[:TELEGRAM_MAX_CAPTION_LENGTH]
            cut = len(caption)
        remainder = text[cut:].lstrip("\n")
        follow_ups = (
            split_telegram_text(remainder, TELEGRAM_MAX_MESSAGE_LENGTH) if remainder else []
        )

        primary = await self.send_photo(
            chat_id,
            image_url,
            caption=caption,
            button=button if not follow_ups else None,
            parse_mode=parse_mode,
        )
        for index, chunk in enumerate(follow_ups):
            is_last = index == len(follow_ups) - 1
            await self.send_text(
                chat_id,
                chunk,
                button=button if is_last else None,
                parse_mode=parse_mode,
            )
        return primary

    def _build_inline_keyboard(self, button: InlineUrlButton) -> str:
        keyboard = {
            "inline_keyboard": [[{"text": button.text, "url": button.url}]],
        }
        return json.dumps(keyboard)

    async def _post(self, method: str, payload: dict) -> dict:
        url = f"{self.base_url}/bot{self.bot_token}/{method}"
        last_error: TelegramPublishError | None = None

        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt_index in range(TELEGRAM_MAX_RETRIES + 1):
                try:
                    response = await client.post(url, json=payload)
                except httpx.HTTPError as exc:
                    last_error = TelegramPublishError(
                        f"Telegram API request failed: {exc}",
                    )
                    if attempt_index < TELEGRAM_MAX_RETRIES:
                        await asyncio.sleep(self._backoff_delay(attempt_index))
                        continue
                    raise last_error from exc

                data, parse_error = self._parse_response_json(response)
                if parse_error is not None:
                    last_error = TelegramPublishError(
                        f"Telegram API returned invalid JSON: {parse_error}",
                        http_status=response.status_code,
                    )
                    if self._should_retry_http_status(response.status_code) and (
                        attempt_index < TELEGRAM_MAX_RETRIES
                    ):
                        await asyncio.sleep(self._backoff_delay(attempt_index))
                        continue
                    raise last_error

                if self._is_rate_limited(response, data):
                    retry_after = self._extract_retry_after(data)
                    last_error = TelegramPublishError(
                        data.get("description", "Telegram rate limit exceeded"),
                        http_status=429,
                        telegram_error_code=data.get("error_code", 429),
                        retry_after=retry_after,
                    )
                    if attempt_index < TELEGRAM_MAX_RETRIES:
                        await asyncio.sleep(self._rate_limit_delay(retry_after, attempt_index))
                        continue
                    raise last_error

                if response.status_code >= 500:
                    last_error = TelegramPublishError(
                        data.get(
                            "description",
                            f"Telegram API HTTP {response.status_code}",
                        ),
                        http_status=response.status_code,
                        telegram_error_code=data.get("error_code"),
                    )
                    if attempt_index < TELEGRAM_MAX_RETRIES:
                        await asyncio.sleep(self._backoff_delay(attempt_index))
                        continue
                    raise last_error

                if data.get("ok"):
                    return data

                error_code = data.get("error_code")
                description = data.get("description", "Telegram API request failed")
                if self._is_retryable_telegram_error_code(error_code):
                    last_error = TelegramPublishError(
                        description,
                        http_status=response.status_code,
                        telegram_error_code=error_code,
                    )
                    if attempt_index < TELEGRAM_MAX_RETRIES:
                        await asyncio.sleep(self._backoff_delay(attempt_index))
                        continue
                    raise last_error

                # Non-transient client/API failure — do not consume retry budget.
                raise TelegramPublishError(
                    description,
                    http_status=response.status_code if response.status_code >= 400 else None,
                    telegram_error_code=error_code,
                )

        assert last_error is not None
        raise last_error

    def _parse_response_json(self, response: httpx.Response) -> tuple[dict, Exception | None]:
        try:
            data = response.json()
        except (ValueError, json.JSONDecodeError) as exc:
            return {}, exc
        if not isinstance(data, dict):
            return {}, ValueError("Telegram API response JSON was not an object")
        return data, None

    def _is_rate_limited(self, response: httpx.Response, data: dict) -> bool:
        if response.status_code == 429:
            return True
        if data.get("error_code") == 429:
            return True
        parameters = data.get("parameters")
        if (
            isinstance(parameters, dict)
            and parameters.get("retry_after") is not None
            and data.get("ok") is False
        ):
            return True
        return False

    def _extract_retry_after(self, data: dict) -> float | int | None:
        parameters = data.get("parameters")
        if not isinstance(parameters, dict):
            return None
        retry_after = parameters.get("retry_after")
        if isinstance(retry_after, (int, float)) and retry_after >= 0:
            return retry_after
        return None

    def _is_retryable_telegram_error_code(self, error_code: object) -> bool:
        return isinstance(error_code, int) and error_code >= 500

    def _should_retry_http_status(self, status_code: int) -> bool:
        return status_code >= 500 or status_code == 429

    def _backoff_delay(self, attempt_index: int) -> float:
        return (TELEGRAM_BASE_BACKOFF_SECONDS * (2**attempt_index)) + random.uniform(
            0,
            TELEGRAM_JITTER_SECONDS,
        )

    def _rate_limit_delay(
        self,
        retry_after: float | int | None,
        attempt_index: int,
    ) -> float:
        if retry_after is None:
            return self._backoff_delay(attempt_index)
        # Honor Telegram's retry_after exactly, with a small optional jitter.
        return float(retry_after) + random.uniform(0, TELEGRAM_JITTER_SECONDS)
