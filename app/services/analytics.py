from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.analytics_repository import AnalyticsRepository
from app.repositories.campaign import CampaignRepository
from app.schemas.analytics import (
    AnalyticsCampaignFunnelResponse,
    AnalyticsDayPoint,
    AnalyticsOverviewResponse,
)
from app.services.exceptions import NotFoundError, ValidationError

DEFAULT_RANGE_DAYS = 30
MAX_RANGE_DAYS = 366
MAX_BY_DAY_POINTS = 366


def conversion_rate(clicks: int, conversions: int) -> float:
    if clicks == 0:
        return 0.0
    return round(conversions / clicks, 4)


def resolve_analytics_window(
    range_from: datetime | None,
    range_to: datetime | None,
    *,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    else:
        current = current.astimezone(UTC)

    end = _as_utc(range_to) if range_to is not None else current
    start = (
        _as_utc(range_from)
        if range_from is not None
        else end - timedelta(days=DEFAULT_RANGE_DAYS)
    )

    if start > end:
        raise ValidationError("Invalid date range")
    if end - start > timedelta(days=MAX_RANGE_DAYS):
        raise ValidationError("Date range cannot exceed 1 year")
    return start, end


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _fill_by_day(
    buckets: list,
    range_from: datetime,
    range_to: datetime,
) -> list[AnalyticsDayPoint]:
    by_day = {item.day: item for item in buckets}
    start_day = range_from.date()
    end_day = range_to.date()
    days = (end_day - start_day).days + 1
    if days > MAX_BY_DAY_POINTS:
        raise ValidationError("Date range cannot exceed 1 year")
    points: list[AnalyticsDayPoint] = []
    cursor = start_day
    while cursor <= end_day:
        bucket = by_day.get(cursor)
        points.append(
            AnalyticsDayPoint(
                date=cursor,
                clicks=bucket.clicks if bucket else 0,
                conversions=bucket.conversions if bucket else 0,
            )
        )
        cursor = date.fromordinal(cursor.toordinal() + 1)
    return points


class AnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.analytics_repo = AnalyticsRepository(session)
        self.campaign_repo = CampaignRepository(session)

    async def get_overview(
        self,
        workspace_id: UUID,
        *,
        range_from: datetime | None,
        range_to: datetime | None,
    ) -> AnalyticsOverviewResponse:
        start, end = resolve_analytics_window(range_from, range_to)
        totals = await self.analytics_repo.get_workspace_totals(
            workspace_id,
            range_from=start,
            range_to=end,
        )
        buckets = await self.analytics_repo.get_workspace_by_day(
            workspace_id,
            range_from=start,
            range_to=end,
        )
        return AnalyticsOverviewResponse(
            range_from=start,
            range_to=end,
            total_clicks=totals.clicks,
            total_conversions=totals.conversions,
            conversion_rate=conversion_rate(totals.clicks, totals.conversions),
            total_revenue=totals.revenue,
            by_day=_fill_by_day(buckets, start, end),
        )

    async def get_campaign_funnel(
        self,
        workspace_id: UUID,
        campaign_id: UUID,
        *,
        range_from: datetime | None,
        range_to: datetime | None,
    ) -> AnalyticsCampaignFunnelResponse:
        campaign = await self.campaign_repo.get_by_id_in_workspace(campaign_id, workspace_id)
        if campaign is None:
            raise NotFoundError("Campaign not found")
        start, end = resolve_analytics_window(range_from, range_to)
        totals = await self.analytics_repo.get_workspace_totals(
            workspace_id,
            range_from=start,
            range_to=end,
            campaign_id=campaign.id,
        )
        buckets = await self.analytics_repo.get_workspace_by_day(
            workspace_id,
            range_from=start,
            range_to=end,
            campaign_id=campaign.id,
        )
        return AnalyticsCampaignFunnelResponse(
            campaign_id=campaign.id,
            campaign_name=campaign.name,
            range_from=start,
            range_to=end,
            total_clicks=totals.clicks,
            total_conversions=totals.conversions,
            attributed_conversions=totals.attributed_conversions,
            conversion_rate=conversion_rate(totals.clicks, totals.conversions),
            total_revenue=totals.revenue,
            by_day=_fill_by_day(buckets, start, end),
        )
