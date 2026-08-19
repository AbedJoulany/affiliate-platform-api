from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import CampaignStatus
from app.models.campaign import Campaign
from app.repositories.base import BaseRepository


class CampaignRepository(BaseRepository[Campaign]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Campaign)

    async def get_by_id_in_workspace(
        self,
        campaign_id: UUID,
        workspace_id: UUID,
    ) -> Campaign | None:
        result = await self.session.execute(
            select(Campaign).where(
                Campaign.id == campaign_id,
                Campaign.workspace_id == workspace_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_in_workspace(
        self,
        workspace_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Campaign]:
        result = await self.session.execute(
            select(Campaign)
            .where(Campaign.workspace_id == workspace_id)
            .offset(skip)
            .limit(limit)
            .order_by(Campaign.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_active_in_workspace(
        self,
        workspace_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Campaign]:
        result = await self.session.execute(
            select(Campaign)
            .where(
                Campaign.status == CampaignStatus.ACTIVE,
                Campaign.workspace_id == workspace_id,
            )
            .offset(skip)
            .limit(limit)
            .order_by(Campaign.created_at.desc())
        )
        return list(result.scalars().all())
