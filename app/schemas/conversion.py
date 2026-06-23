from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.enums import ConversionStatus
from app.schemas.common import TimestampSchema


class ConversionCreate(BaseModel):
    affiliate_id: UUID
    campaign_id: UUID
    external_order_id: str = Field(min_length=1, max_length=128)
    amount: Decimal = Field(gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    click_id: str | None = Field(default=None, max_length=64)


class ConversionUpdate(BaseModel):
    status: ConversionStatus


class ConversionRead(TimestampSchema):
    id: UUID
    affiliate_id: UUID
    campaign_id: UUID
    external_order_id: str
    amount: Decimal
    commission: Decimal
    currency: str
    status: ConversionStatus
    click_id: str | None
