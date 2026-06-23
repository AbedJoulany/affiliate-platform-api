from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from app.core.config import get_settings
from app.models.enums import BotPermissionStatus
from app.telegram.validators import normalize_telegram_channel_id

settings = get_settings()


@dataclass
class BotPermissionsResult:
    status: BotPermissionStatus
    title: str | None = None
    username: str | None = None
    can_post_messages: bool = False
    can_edit_messages: bool = False
    can_delete_messages: bool = False
    checked_at: datetime | None = None
    detail: str | None = None


class TelegramBotClient:
    def __init__(self, bot_token: str | None = None) -> None:
        self.bot_token = bot_token or settings.telegram_bot_token
        self.base_url = settings.telegram_api_base_url.rstrip("/")

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token)

    async def check_channel_permissions(self, channel_id: str) -> BotPermissionsResult:
        normalized_id = normalize_telegram_channel_id(channel_id)

        if not self.is_configured:
            return BotPermissionsResult(
                status=BotPermissionStatus.UNKNOWN,
                detail="Telegram bot token is not configured",
            )

        async with httpx.AsyncClient(timeout=15.0) as client:
            bot_info = await self._api_call(client, "getMe")
            if not bot_info.get("ok"):
                return BotPermissionsResult(
                    status=BotPermissionStatus.UNKNOWN,
                    detail=bot_info.get("description", "Failed to authenticate bot"),
                )

            bot_id = bot_info["result"]["id"]

            chat_info = await self._api_call(
                client,
                "getChat",
                params={"chat_id": normalized_id},
            )
            if not chat_info.get("ok"):
                return BotPermissionsResult(
                    status=BotPermissionStatus.DENIED,
                    checked_at=datetime.now(UTC),
                    detail=chat_info.get("description", "Channel not found or bot has no access"),
                )

            chat = chat_info["result"]
            member_info = await self._api_call(
                client,
                "getChatMember",
                params={"chat_id": normalized_id, "user_id": bot_id},
            )
            if not member_info.get("ok"):
                return BotPermissionsResult(
                    status=BotPermissionStatus.DENIED,
                    title=chat.get("title"),
                    username=chat.get("username"),
                    checked_at=datetime.now(UTC),
                    detail=member_info.get("description", "Bot is not a member of this channel"),
                )

            member = member_info["result"]
            status_value = member.get("status", "")
            if status_value not in {"administrator", "creator"}:
                return BotPermissionsResult(
                    status=BotPermissionStatus.DENIED,
                    title=chat.get("title"),
                    username=chat.get("username"),
                    checked_at=datetime.now(UTC),
                    detail=f"Bot status in channel: {status_value}",
                )

            can_post = bool(member.get("can_post_messages", False))
            can_edit = bool(member.get("can_edit_messages", False))
            can_delete = bool(member.get("can_delete_messages", False))

            if can_post and can_edit and can_delete:
                permission_status = BotPermissionStatus.GRANTED
            elif can_post or can_edit or can_delete:
                permission_status = BotPermissionStatus.PARTIAL
            else:
                permission_status = BotPermissionStatus.DENIED

            return BotPermissionsResult(
                status=permission_status,
                title=chat.get("title"),
                username=chat.get("username"),
                can_post_messages=can_post,
                can_edit_messages=can_edit,
                can_delete_messages=can_delete,
                checked_at=datetime.now(UTC),
            )

    async def _api_call(
        self,
        client: httpx.AsyncClient,
        method: str,
        *,
        params: dict | None = None,
    ) -> dict:
        url = f"{self.base_url}/bot{self.bot_token}/{method}"
        response = await client.get(url, params=params or {})
        response.raise_for_status()
        return response.json()
