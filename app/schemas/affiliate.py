from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from app.core.enums import AffiliateStatus
from app.schemas.common import TimestampSchema


class AffiliateCreate(BaseModel):
    company_name: str | None = Field(default=None, max_length=255)
    website: HttpUrl | str | None = None
    payout_details: str | None = None


class AffiliateUpdate(BaseModel):
    company_name: str | None = Field(default=None, max_length=255)
    website: HttpUrl | str | None = None
    payout_details: str | None = None
    status: AffiliateStatus | None = None
    commission_rate: Decimal | None = Field(default=None, ge=0, le=100)


class AffiliateRead(TimestampSchema):
    id: UUID
    user_id: UUID
    company_name: str | None
    website: str | None
    referral_code: str
    status: AffiliateStatus
    commission_rate: Decimal
    payout_details: str | None


class AffiliateCampaignJoin(BaseModel):
    campaign_id: UUID


class AffiliateCampaignRead(TimestampSchema):
    id: UUID
    affiliate_id: UUID
    campaign_id: UUID
    tracking_link: str
