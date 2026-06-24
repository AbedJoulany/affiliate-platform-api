from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from app.core.enums import CampaignStatus
from app.schemas.common import TimestampSchema


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    payout_amount: Decimal = Field(gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    landing_url: HttpUrl | str
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class CampaignUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: CampaignStatus | None = None
    payout_amount: Decimal | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    landing_url: HttpUrl | str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class CampaignRead(TimestampSchema):
    id: UUID
    name: str
    description: str | None
    advertiser_id: UUID | None
    status: CampaignStatus
    payout_amount: Decimal
    currency: str
    landing_url: str
    starts_at: datetime | None
    ends_at: datetime | None
