from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models.affiliate import AffiliateCampaign
from app.models.campaign import Campaign
from app.models.click import Click
from app.models.conversion import Conversion


@dataclass(frozen=True)
class AnalyticsTotals:
    clicks: int
    conversions: int
    attributed_conversions: int
    revenue: Decimal


@dataclass(frozen=True)
class AnalyticsDayBucket:
    day: date
    clicks: int
    conversions: int


class AnalyticsRepository:
    """Read-only aggregates over clicks and conversions. Never writes."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _day_expr(self, column: ColumnElement[datetime]) -> ColumnElement[object]:
        dialect = self.session.bind.dialect.name if self.session.bind is not None else "postgresql"
        if dialect == "postgresql":
            return func.date_trunc("day", column)
        return func.strftime("%Y-%m-%d", column)

    async def get_workspace_totals(
        self,
        workspace_id: UUID,
        *,
        range_from: datetime,
        range_to: datetime,
        campaign_id: UUID | None = None,
    ) -> AnalyticsTotals:
        click_filters = [
            Click.created_at >= range_from,
            Click.created_at <= range_to,
        ]
        conversion_filters = [
            Conversion.created_at >= range_from,
            Conversion.created_at <= range_to,
        ]
        if campaign_id is not None:
            click_filters.append(AffiliateCampaign.campaign_id == campaign_id)
            conversion_filters.append(Conversion.campaign_id == campaign_id)

        click_stmt = (
            select(func.count(Click.id))
            .select_from(Click)
            .join(AffiliateCampaign, AffiliateCampaign.id == Click.affiliate_campaign_id)
            .join(Campaign, Campaign.id == AffiliateCampaign.campaign_id)
            .where(Campaign.workspace_id == workspace_id, *click_filters)
        )
        conversion_stmt = (
            select(
                func.count(Conversion.id),
                func.coalesce(func.sum(Conversion.amount), 0),
            )
            .select_from(Conversion)
            .join(Campaign, Campaign.id == Conversion.campaign_id)
            .where(Campaign.workspace_id == workspace_id, *conversion_filters)
        )

        clicks = int((await self.session.execute(click_stmt)).scalar_one())
        conversion_row = (await self.session.execute(conversion_stmt)).one()
        conversions = int(conversion_row[0])
        revenue = Decimal(str(conversion_row[1] or 0)).quantize(Decimal("0.01"))

        attributed = 0
        if campaign_id is not None:
            matched_click_ids = (
                select(Click.click_id)
                .join(AffiliateCampaign, AffiliateCampaign.id == Click.affiliate_campaign_id)
                .where(AffiliateCampaign.campaign_id == campaign_id)
            )
            attributed_stmt = (
                select(func.count(Conversion.id))
                .select_from(Conversion)
                .join(Campaign, Campaign.id == Conversion.campaign_id)
                .where(
                    Campaign.workspace_id == workspace_id,
                    *conversion_filters,
                    Conversion.click_id.in_(matched_click_ids),
                )
            )
            attributed = int((await self.session.execute(attributed_stmt)).scalar_one())

        return AnalyticsTotals(
            clicks=clicks,
            conversions=conversions,
            attributed_conversions=attributed,
            revenue=revenue,
        )

    async def get_workspace_by_day(
        self,
        workspace_id: UUID,
        *,
        range_from: datetime,
        range_to: datetime,
        campaign_id: UUID | None = None,
    ) -> list[AnalyticsDayBucket]:
        click_day = self._day_expr(Click.created_at)
        conversion_day = self._day_expr(Conversion.created_at)

        click_filters = [
            Click.created_at >= range_from,
            Click.created_at <= range_to,
        ]
        conversion_filters = [
            Conversion.created_at >= range_from,
            Conversion.created_at <= range_to,
        ]
        if campaign_id is not None:
            click_filters.append(AffiliateCampaign.campaign_id == campaign_id)
            conversion_filters.append(Conversion.campaign_id == campaign_id)

        click_stmt = (
            select(click_day.label("day"), func.count(Click.id).label("clicks"))
            .select_from(Click)
            .join(AffiliateCampaign, AffiliateCampaign.id == Click.affiliate_campaign_id)
            .join(Campaign, Campaign.id == AffiliateCampaign.campaign_id)
            .where(Campaign.workspace_id == workspace_id, *click_filters)
            .group_by(click_day)
        )
        conversion_stmt = (
            select(
                conversion_day.label("day"),
                func.count(Conversion.id).label("conversions"),
            )
            .select_from(Conversion)
            .join(Campaign, Campaign.id == Conversion.campaign_id)
            .where(Campaign.workspace_id == workspace_id, *conversion_filters)
            .group_by(conversion_day)
        )

        click_rows = (await self.session.execute(click_stmt)).all()
        conversion_rows = (await self.session.execute(conversion_stmt)).all()
        clicks_by_day = {_as_date(row.day): int(row.clicks) for row in click_rows}
        conversions_by_day = {
            _as_date(row.day): int(row.conversions) for row in conversion_rows
        }
        days = sorted(set(clicks_by_day) | set(conversions_by_day))
        return [
            AnalyticsDayBucket(
                day=day,
                clicks=clicks_by_day.get(day, 0),
                conversions=conversions_by_day.get(day, 0),
            )
            for day in days
        ]


def _as_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])
