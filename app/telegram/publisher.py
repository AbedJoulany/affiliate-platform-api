import json

import httpx

from app.core.config import get_settings
from app.services.exceptions import TelegramPublishError, ValidationError
from app.telegram.types import InlineUrlButton, TelegramPublishResult

settings = get_settings()


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
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, json=payload)
                data = response.json()
            except httpx.HTTPError as exc:
                raise TelegramPublishError(f"Telegram API request failed: {exc}") from exc

        if not data.get("ok"):
            raise TelegramPublishError(data.get("description", "Telegram API request failed"))

        return data
