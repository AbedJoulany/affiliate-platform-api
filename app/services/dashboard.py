from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProductStatus, QueueStatus
from app.repositories.dashboard import DashboardRepository
from app.schemas.dashboard import (
    ChannelCounts,
    DashboardAttentionItem,
    DashboardAutomation,
    DashboardDestinationReadiness,
    DashboardPublishing,
    DashboardReporting,
    DashboardResponse,
    DashboardSystemStatus,
    FacebookDestinationReadiness,
    ProductTotals,
    PublishingByProvider,
    PublishingProviderCounts,
    QueueCounts,
    RecentActivity,
    TelegramDestinationReadiness,
)


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self.dashboard_repo = DashboardRepository(session)

    async def get_dashboard(
        self,
        workspace_id: UUID,
        *,
        activity_limit: int = 10,
        now: datetime | None = None,
    ) -> DashboardResponse:
        generated_at = self._as_utc(now or datetime.now(UTC))
        timezone_name = await self.dashboard_repo.get_workspace_timezone(workspace_id)
        reporting = self._reporting_window(timezone_name, generated_at)
        snapshot = await self.dashboard_repo.get_snapshot(
            workspace_id,
            activity_limit=activity_limit,
            day_start_utc=reporting.day_start_utc,
            day_end_utc=reporting.day_end_utc,
        )
        product_counts = {
            status: snapshot.product_counts.get(status, 0) for status in ProductStatus
        }
        queue_counts = {
            status: snapshot.queue_counts.get(status, 0) for status in QueueStatus
        }
        return DashboardResponse(
            products=ProductTotals(
                total=sum(product_counts.values()),
                by_status=product_counts,
            ),
            queue=QueueCounts(
                total=sum(queue_counts.values()),
                by_status=queue_counts,
            ),
            channels=ChannelCounts(
                total=snapshot.channel_total,
                active=snapshot.active_channels,
                inactive=snapshot.channel_total - snapshot.active_channels,
            ),
            recent_activity=[
                RecentActivity(
                    resource_type=item.resource_type,
                    resource_id=item.resource_id,
                    title=item.title,
                    status=item.status,
                    occurred_at=item.occurred_at,
                )
                for item in snapshot.recent_activity
            ],
            system_status=DashboardSystemStatus(
                status="operational",
                database="up",
                generated_at=reporting.generated_at,
            ),
            reporting=DashboardReporting(
                timezone=reporting.timezone,
                day_start_utc=reporting.day_start_utc,
                day_end_utc=reporting.day_end_utc,
                generated_at=reporting.generated_at,
            ),
            publishing=DashboardPublishing(
                published_today=snapshot.publishing.published_today,
                failed_today=snapshot.publishing.failed_today,
                ambiguous_unresolved=snapshot.publishing.ambiguous_unresolved,
                by_provider=PublishingByProvider(
                    telegram=PublishingProviderCounts(
                        published=snapshot.publishing.by_provider["telegram"].published,
                        failed=snapshot.publishing.by_provider["telegram"].failed,
                    ),
                    facebook=PublishingProviderCounts(
                        published=snapshot.publishing.by_provider["facebook"].published,
                        failed=snapshot.publishing.by_provider["facebook"].failed,
                    ),
                ),
            ),
            attention_items=[
                DashboardAttentionItem(
                    queue_id=item.queue_id,
                    title=item.title,
                    provider=item.provider,
                    issue=item.issue,
                    error_code=item.error_code,
                    message=item.message,
                    occurred_at=item.occurred_at,
                )
                for item in snapshot.attention_items
            ],
            destination_readiness=DashboardDestinationReadiness(
                telegram=TelegramDestinationReadiness(
                    total=snapshot.destination_readiness.telegram.total,
                    active=snapshot.destination_readiness.telegram.active,
                    permission_granted=(
                        snapshot.destination_readiness.telegram.permission_granted
                    ),
                ),
                facebook=FacebookDestinationReadiness(
                    total=snapshot.destination_readiness.facebook.total,
                    active=snapshot.destination_readiness.facebook.active,
                    validated=snapshot.destination_readiness.facebook.validated,
                    publishing_permission_verified=(
                        snapshot.destination_readiness.facebook.publishing_permission_verified
                    ),
                ),
            ),
            automation=DashboardAutomation(
                status="not_configured",
                last_run_at=None,
            ),
        )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _reporting_window(
        timezone_name: str | None,
        generated_at: datetime,
    ) -> "ReportingWindow":
        try:
            timezone = ZoneInfo(timezone_name or "UTC")
            resolved_name = timezone_name or "UTC"
        except (TypeError, ValueError, ZoneInfoNotFoundError):
            timezone = ZoneInfo("UTC")
            resolved_name = "UTC"

        local_date = generated_at.astimezone(timezone).date()
        local_start = datetime.combine(local_date, time.min, tzinfo=timezone)
        local_end = datetime.combine(
            local_date + timedelta(days=1),
            time.min,
            tzinfo=timezone,
        )
        return ReportingWindow(
            timezone=resolved_name,
            day_start_utc=local_start.astimezone(UTC),
            day_end_utc=local_end.astimezone(UTC),
            generated_at=generated_at,
        )


@dataclass(frozen=True)
class ReportingWindow:
    timezone: str
    day_start_utc: datetime
    day_end_utc: datetime
    generated_at: datetime
