from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.channel import TelegramChannel
from app.repositories.base import BaseRepository


class ChannelRepository(BaseRepository[TelegramChannel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TelegramChannel)

    async def get_by_id_in_workspace(
        self,
        channel_id: UUID,
        workspace_id: UUID,
    ) -> TelegramChannel | None:
        result = await self.session.execute(
            select(TelegramChannel).where(
                TelegramChannel.id == channel_id,
                TelegramChannel.workspace_id == workspace_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_telegram_channel_id(
        self,
        telegram_channel_id: str,
    ) -> TelegramChannel | None:
        result = await self.session.execute(
            select(TelegramChannel).where(
                TelegramChannel.telegram_channel_id == telegram_channel_id
            )
        )
        return result.scalar_one_or_none()

    async def list_in_workspace(
        self,
        workspace_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[TelegramChannel], int]:
        filters = (TelegramChannel.workspace_id == workspace_id,)
        count_result = await self.session.execute(
            select(func.count()).select_from(TelegramChannel).where(*filters)
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            select(TelegramChannel)
            .where(*filters)
            .order_by(TelegramChannel.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total
