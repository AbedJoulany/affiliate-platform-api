from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.channel import TelegramChannel
from app.repositories.base import BaseRepository


class ChannelRepository(BaseRepository[TelegramChannel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TelegramChannel)

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

    async def list_channels(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[TelegramChannel], int]:
        count_result = await self.session.execute(
            select(func.count()).select_from(TelegramChannel)
        )
        total = count_result.scalar_one()

        result = await self.session.execute(
            select(TelegramChannel)
            .order_by(TelegramChannel.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all()), total
