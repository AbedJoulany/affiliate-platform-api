from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import Campaign
from app.models.enums import CampaignStatus
from app.repositories.base import BaseRepository


class CampaignRepository(BaseRepository[Campaign]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Campaign)

    async def list_active(self, *, skip: int = 0, limit: int = 100) -> list[Campaign]:
        result = await self.session.execute(
            select(Campaign)
            .where(Campaign.status == CampaignStatus.ACTIVE)
            .offset(skip)
            .limit(limit)
            .order_by(Campaign.created_at.desc())
        )
        return list(result.scalars().all())
