from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.channel import TelegramChannel
from app.core.enums import BotPermissionStatus
from app.models.channel import TelegramChannel
from app.repositories.channel import ChannelRepository
from app.schemas.channel import ChannelCreate, ChannelListResponse, ChannelUpdate
from app.services.exceptions import ConflictError, NotFoundError
from app.telegram.client import BotPermissionsResult, TelegramBotClient


class ChannelService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.channel_repo = ChannelRepository(session)
        self.telegram_client = TelegramBotClient()

    async def create(self, payload: ChannelCreate) -> TelegramChannel:
        existing = await self.channel_repo.get_by_telegram_channel_id(payload.telegram_channel_id)
        if existing:
            raise ConflictError("Telegram channel already registered")

        permissions = await self.telegram_client.check_channel_permissions(
            payload.telegram_channel_id
        )

        channel = TelegramChannel(
            telegram_channel_id=payload.telegram_channel_id,
            title=payload.title or permissions.title,
            username=permissions.username,
            is_active=payload.is_active,
        )
        self._apply_permissions(channel, permissions)
        return await self.channel_repo.create(channel)

    async def list_channels(self, *, skip: int = 0, limit: int = 100) -> ChannelListResponse:
        items, total = await self.channel_repo.list_channels(skip=skip, limit=limit)
        return ChannelListResponse(items=items, total=total, skip=skip, limit=limit)

    async def update(self, channel_id: UUID, payload: ChannelUpdate) -> TelegramChannel:
        channel = await self._get_or_404(channel_id)

        if payload.telegram_channel_id and payload.telegram_channel_id != channel.telegram_channel_id:
            existing = await self.channel_repo.get_by_telegram_channel_id(payload.telegram_channel_id)
            if existing:
                raise ConflictError("Telegram channel already registered")
            channel.telegram_channel_id = payload.telegram_channel_id

        if payload.title is not None:
            channel.title = payload.title
        if payload.is_active is not None:
            channel.is_active = payload.is_active

        if payload.telegram_channel_id is not None:
            permissions = await self.telegram_client.check_channel_permissions(
                channel.telegram_channel_id
            )
            self._apply_permissions(channel, permissions)
            if permissions.title and payload.title is None:
                channel.title = permissions.title

        return await self.channel_repo.update(channel)

    async def delete(self, channel_id: UUID) -> None:
        channel = await self._get_or_404(channel_id)
        await self.channel_repo.delete(channel)

    async def refresh_permissions(self, channel_id: UUID) -> TelegramChannel:
        channel = await self._get_or_404(channel_id)
        permissions = await self.telegram_client.check_channel_permissions(
            channel.telegram_channel_id
        )
        self._apply_permissions(channel, permissions)
        if permissions.title:
            channel.title = permissions.title
        channel.username = permissions.username
        return await self.channel_repo.update(channel)

    async def _get_or_404(self, channel_id: UUID) -> TelegramChannel:
        channel = await self.channel_repo.get_by_id(channel_id)
        if not channel:
            raise NotFoundError("Channel not found")
        return channel

    def _apply_permissions(
        self,
        channel: TelegramChannel,
        permissions: BotPermissionsResult,
    ) -> None:
        channel.bot_permission_status = permissions.status
        channel.can_post_messages = permissions.can_post_messages
        channel.can_edit_messages = permissions.can_edit_messages
        channel.can_delete_messages = permissions.can_delete_messages
        channel.permissions_checked_at = permissions.checked_at
        channel.permission_detail = permissions.detail
        if permissions.username:
            channel.username = permissions.username
