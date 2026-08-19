from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ConversionStatus, UserRole
from app.models.conversion import Conversion
from app.models.user import User
from app.repositories.affiliate import AffiliateCampaignRepository, AffiliateRepository
from app.repositories.campaign import CampaignRepository
from app.repositories.conversion import ConversionRepository
from app.repositories.workspace import WorkspaceMembershipRepository
from app.schemas.conversion import ConversionCreate, ConversionUpdate
from app.services.exceptions import ConflictError, ForbiddenError, NotFoundError


class ConversionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.conversion_repo = ConversionRepository(session)
        self.affiliate_repo = AffiliateRepository(session)
        self.campaign_repo = CampaignRepository(session)
        self.link_repo = AffiliateCampaignRepository(session)
        self.membership_repo = WorkspaceMembershipRepository(session)

    async def record_conversion(
        self,
        user: User,
        payload: ConversionCreate,
        workspace_id: UUID,
    ) -> Conversion:
        existing = await self.conversion_repo.get_by_external_order_id(payload.external_order_id)
        if existing:
            raise ConflictError("Conversion with this order ID already exists")

        affiliate = await self.affiliate_repo.get_by_id(payload.affiliate_id)
        if not affiliate:
            raise NotFoundError("Affiliate not found")

        if user.role != UserRole.ADMIN and affiliate.user_id != user.id:
            raise ForbiddenError("Insufficient permissions")

        campaign = await self.campaign_repo.get_by_id_in_workspace(
            payload.campaign_id,
            workspace_id,
        )
        if not campaign:
            raise NotFoundError("Campaign not found")

        affiliate_membership = await self.membership_repo.get_membership(
            workspace_id,
            affiliate.user_id,
        )
        if affiliate_membership is None:
            raise NotFoundError("Affiliate not found")

        link = await self.link_repo.get_by_affiliate_and_campaign(
            payload.affiliate_id,
            payload.campaign_id,
        )
        if not link:
            raise ForbiddenError("Affiliate is not enrolled in this campaign")

        commission = (payload.amount * affiliate.commission_rate / Decimal("100")).quantize(
            Decimal("0.01")
        )

        conversion = Conversion(
            affiliate_id=payload.affiliate_id,
            campaign_id=payload.campaign_id,
            external_order_id=payload.external_order_id,
            amount=payload.amount,
            commission=commission,
            currency=payload.currency,
            click_id=payload.click_id,
            status=ConversionStatus.PENDING,
        )
        return await self.conversion_repo.create(conversion)

    async def update_status(
        self,
        user: User,
        conversion_id: UUID,
        payload: ConversionUpdate,
        workspace_id: UUID,
    ) -> Conversion:
        if user.role != UserRole.ADMIN:
            raise ForbiddenError("Only admins can update conversion status")

        conversion = await self.conversion_repo.get_by_id_in_workspace(
            conversion_id,
            workspace_id,
        )
        if not conversion:
            raise NotFoundError("Conversion not found")

        conversion.status = payload.status
        return await self.conversion_repo.update(conversion)

    async def list_for_affiliate(
        self,
        user: User,
        workspace_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Conversion]:
        affiliate = await self.affiliate_repo.get_by_user_id(user.id)
        if not affiliate:
            raise NotFoundError("Affiliate profile not found")

        return await self.conversion_repo.list_by_affiliate_in_workspace(
            affiliate.id,
            workspace_id,
            skip=skip,
            limit=limit,
        )

    async def list_all(
        self,
        user: User,
        workspace_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Conversion]:
        if user.role != UserRole.ADMIN:
            raise ForbiddenError("Only admins can list all conversions")
        return await self.conversion_repo.list_in_workspace(
            workspace_id,
            skip=skip,
            limit=limit,
        )
