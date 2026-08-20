from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import CampaignStatus, UserRole
from app.models.affiliate import Affiliate, AffiliateCampaign
from app.models.user import User
from app.repositories.affiliate import AffiliateCampaignRepository, AffiliateRepository
from app.repositories.campaign import CampaignRepository
from app.schemas.affiliate import AffiliateCreate, AffiliateUpdate
from app.services.exceptions import ConflictError, ForbiddenError, NotFoundError


class AffiliateService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.affiliate_repo = AffiliateRepository(session)
        self.campaign_repo = CampaignRepository(session)
        self.link_repo = AffiliateCampaignRepository(session)

    async def get_my_profile(self, user: User) -> Affiliate:
        affiliate = await self.affiliate_repo.get_by_user_id(user.id)
        if not affiliate:
            raise NotFoundError("Affiliate profile not found")
        return affiliate

    async def create_profile(self, user: User, payload: AffiliateCreate) -> Affiliate:
        if user.role != UserRole.AFFILIATE:
            raise ForbiddenError("Only affiliate users can create affiliate profiles")

        existing = await self.affiliate_repo.get_by_user_id(user.id)
        if existing:
            raise ConflictError("Affiliate profile already exists")

        affiliate = Affiliate(
            user_id=user.id,
            company_name=payload.company_name,
            website=str(payload.website) if payload.website else None,
            payout_details=payload.payout_details,
            referral_code=self._generate_unique_code(),
        )
        return await self.affiliate_repo.create(affiliate)

    async def update_profile(
        self,
        user: User,
        affiliate_id: UUID,
        payload: AffiliateUpdate,
    ) -> Affiliate:
        affiliate = await self._get_affiliate_or_404(affiliate_id)
        self._ensure_can_modify(user, affiliate)

        update_data = payload.model_dump(exclude_unset=True)
        privileged_fields = {"status", "commission_rate"}
        if user.role != UserRole.ADMIN and privileged_fields.intersection(update_data):
            raise ForbiddenError(
                "Only administrators can update affiliate status or commission rate"
            )
        if "website" in update_data and update_data["website"] is not None:
            update_data["website"] = str(update_data["website"])

        for field, value in update_data.items():
            setattr(affiliate, field, value)

        return await self.affiliate_repo.update(affiliate)

    async def join_campaign(
        self,
        user: User,
        campaign_id: UUID,
        workspace_id: UUID,
    ) -> AffiliateCampaign:
        affiliate = await self.get_my_profile(user)
        campaign = await self.campaign_repo.get_by_id_in_workspace(campaign_id, workspace_id)
        if not campaign:
            raise NotFoundError("Campaign not found")
        if campaign.status != CampaignStatus.ACTIVE:
            raise ConflictError("Campaign is not active")

        existing = await self.link_repo.get_by_affiliate_and_campaign(affiliate.id, campaign_id)
        if existing:
            raise ConflictError("Already joined this campaign")

        tracking_link = f"{campaign.landing_url}?ref={affiliate.referral_code}&cid={campaign_id}"
        link = AffiliateCampaign(
            affiliate_id=affiliate.id,
            campaign_id=campaign_id,
            tracking_link=tracking_link,
        )
        return await self.link_repo.create(link)

    async def list_affiliates(self, *, skip: int = 0, limit: int = 100) -> list[Affiliate]:
        return await self.affiliate_repo.list_all(skip=skip, limit=limit)

    async def _get_affiliate_or_404(self, affiliate_id: UUID) -> Affiliate:
        affiliate = await self.affiliate_repo.get_by_id(affiliate_id)
        if not affiliate:
            raise NotFoundError("Affiliate not found")
        return affiliate

    def _ensure_can_modify(self, user: User, affiliate: Affiliate) -> None:
        if user.role == UserRole.ADMIN:
            return
        if affiliate.user_id != user.id:
            raise ForbiddenError("Cannot modify another affiliate's profile")

    def _generate_unique_code(self) -> str:
        import secrets
        import string

        alphabet = string.ascii_uppercase + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(10))
