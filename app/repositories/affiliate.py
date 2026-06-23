from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.affiliate import Affiliate, AffiliateCampaign
from app.repositories.base import BaseRepository


class AffiliateRepository(BaseRepository[Affiliate]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Affiliate)

    async def get_by_referral_code(self, referral_code: str) -> Affiliate | None:
        result = await self.session.execute(
            select(Affiliate).where(Affiliate.referral_code == referral_code)
        )
        return result.scalar_one_or_none()

    async def get_by_user_id(self, user_id: UUID) -> Affiliate | None:
        result = await self.session.execute(select(Affiliate).where(Affiliate.user_id == user_id))
        return result.scalar_one_or_none()

    async def get_with_campaigns(self, affiliate_id: UUID) -> Affiliate | None:
        result = await self.session.execute(
            select(Affiliate)
            .options(selectinload(Affiliate.campaign_links).selectinload(AffiliateCampaign.campaign))
            .where(Affiliate.id == affiliate_id)
        )
        return result.scalar_one_or_none()


class AffiliateCampaignRepository(BaseRepository[AffiliateCampaign]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AffiliateCampaign)

    async def get_by_affiliate_and_campaign(
        self,
        affiliate_id: UUID,
        campaign_id: UUID,
    ) -> AffiliateCampaign | None:
        result = await self.session.execute(
            select(AffiliateCampaign).where(
                AffiliateCampaign.affiliate_id == affiliate_id,
                AffiliateCampaign.campaign_id == campaign_id,
            )
        )
        return result.scalar_one_or_none()
