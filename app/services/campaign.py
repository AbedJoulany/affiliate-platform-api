from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import CampaignStatus, UserRole
from app.models.campaign import Campaign
from app.models.user import User
from app.repositories.campaign import CampaignRepository
from app.schemas.campaign import CampaignCreate, CampaignUpdate
from app.services.exceptions import ForbiddenError, NotFoundError


class CampaignService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.campaign_repo = CampaignRepository(session)

    async def create(self, user: User, payload: CampaignCreate) -> Campaign:
        if user.role not in (UserRole.ADMIN, UserRole.ADVERTISER):
            raise ForbiddenError("Only admins and advertisers can create campaigns")

        campaign = Campaign(
            name=payload.name,
            description=payload.description,
            advertiser_id=user.id if user.role == UserRole.ADVERTISER else None,
            payout_amount=payload.payout_amount,
            currency=payload.currency,
            landing_url=str(payload.landing_url),
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            status=CampaignStatus.DRAFT,
        )
        return await self.campaign_repo.create(campaign)

    async def get(self, campaign_id: UUID) -> Campaign:
        campaign = await self.campaign_repo.get_by_id(campaign_id)
        if not campaign:
            raise NotFoundError("Campaign not found")
        return campaign

    async def list_active(self, *, skip: int = 0, limit: int = 100) -> list[Campaign]:
        return await self.campaign_repo.list_active(skip=skip, limit=limit)

    async def list_all(self, *, skip: int = 0, limit: int = 100) -> list[Campaign]:
        return await self.campaign_repo.list_all(skip=skip, limit=limit)

    async def update(self, user: User, campaign_id: UUID, payload: CampaignUpdate) -> Campaign:
        campaign = await self.get(campaign_id)
        self._ensure_can_modify(user, campaign)

        update_data = payload.model_dump(exclude_unset=True)
        if "landing_url" in update_data and update_data["landing_url"] is not None:
            update_data["landing_url"] = str(update_data["landing_url"])

        for field, value in update_data.items():
            setattr(campaign, field, value)

        return await self.campaign_repo.update(campaign)

    def _ensure_can_modify(self, user: User, campaign: Campaign) -> None:
        if user.role == UserRole.ADMIN:
            return
        if user.role == UserRole.ADVERTISER and campaign.advertiser_id == user.id:
            return
        raise ForbiddenError("Cannot modify this campaign")
