from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AnalyticsDayPoint(BaseModel):
    date: date
    clicks: int
    conversions: int


class AnalyticsOverviewResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    range_from: datetime = Field(alias="from")
    range_to: datetime = Field(alias="to")
    total_clicks: int
    total_conversions: int
    conversion_rate: float
    total_revenue: Decimal
    by_day: list[AnalyticsDayPoint]


class AnalyticsCampaignFunnelResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    campaign_id: UUID
    campaign_name: str
    range_from: datetime = Field(alias="from")
    range_to: datetime = Field(alias="to")
    total_clicks: int
    total_conversions: int
    attributed_conversions: int
    conversion_rate: float
    total_revenue: Decimal
    by_day: list[AnalyticsDayPoint]
