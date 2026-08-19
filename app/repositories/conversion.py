from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import Campaign
from app.models.conversion import Conversion
from app.repositories.base import BaseRepository


class ConversionRepository(BaseRepository[Conversion]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Conversion)

    async def get_by_external_order_id(self, external_order_id: str) -> Conversion | None:
        result = await self.session.execute(
            select(Conversion).where(Conversion.external_order_id == external_order_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id_in_workspace(
        self,
        conversion_id: UUID,
        workspace_id: UUID,
    ) -> Conversion | None:
        result = await self.session.execute(
            select(Conversion)
            .join(Campaign, Conversion.campaign_id == Campaign.id)
            .where(
                Conversion.id == conversion_id,
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
    ) -> list[Conversion]:
        result = await self.session.execute(
            select(Conversion)
            .join(Campaign, Conversion.campaign_id == Campaign.id)
            .where(Campaign.workspace_id == workspace_id)
            .offset(skip)
            .limit(limit)
            .order_by(Conversion.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_by_affiliate_in_workspace(
        self,
        affiliate_id: UUID,
        workspace_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Conversion]:
        result = await self.session.execute(
            select(Conversion)
            .join(Campaign, Conversion.campaign_id == Campaign.id)
            .where(
                Conversion.affiliate_id == affiliate_id,
                Campaign.workspace_id == workspace_id,
            )
            .offset(skip)
            .limit(limit)
            .order_by(Conversion.created_at.desc())
        )
        return list(result.scalars().all())
