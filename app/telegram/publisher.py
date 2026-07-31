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
        if image_url:
            return await self.send_photo(
                chat_id,
                image_url,
                caption=text,
                button=button,
                parse_mode=parse_mode,
            )
        return await self.send_text(chat_id, text, button=button, parse_mode=parse_mode)

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
