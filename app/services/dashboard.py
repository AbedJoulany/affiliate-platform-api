from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProductStatus, QueueStatus
from app.repositories.dashboard import DashboardRepository
from app.schemas.dashboard import (
    ChannelCounts,
    DashboardResponse,
    DashboardSystemStatus,
    ProductTotals,
    QueueCounts,
    RecentActivity,
)


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self.dashboard_repo = DashboardRepository(session)

    async def get_dashboard(self, *, activity_limit: int = 10) -> DashboardResponse:
        snapshot = await self.dashboard_repo.get_snapshot(activity_limit=activity_limit)
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
                generated_at=datetime.now(UTC),
            ),
        )
