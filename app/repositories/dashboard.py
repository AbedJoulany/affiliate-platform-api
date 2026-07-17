from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import String, case, cast, func, literal, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProductStatus, QueueStatus
from app.models.channel import TelegramChannel
from app.models.product import Product
from app.models.queue import QueueItem


@dataclass(frozen=True)
class ActivityRecord:
    resource_type: str
    resource_id: UUID
    title: str
    status: str
    occurred_at: datetime


@dataclass(frozen=True)
class DashboardSnapshot:
    product_counts: dict[ProductStatus, int]
    queue_counts: dict[QueueStatus, int]
    channel_total: int
    active_channels: int
    recent_activity: list[ActivityRecord]


class DashboardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_snapshot(self, *, activity_limit: int = 10) -> DashboardSnapshot:
        product_counts = await self._product_counts()
        queue_counts = await self._queue_counts()
        channel_total, active_channels = await self._channel_counts()
        recent_activity = await self._recent_activity(limit=activity_limit)
        return DashboardSnapshot(
            product_counts=product_counts,
            queue_counts=queue_counts,
            channel_total=channel_total,
            active_channels=active_channels,
            recent_activity=recent_activity,
        )

    async def _product_counts(self) -> dict[ProductStatus, int]:
        result = await self.session.execute(
            select(Product.status, func.count(Product.id)).group_by(Product.status)
        )
        return {status: count for status, count in result.all()}

    async def _queue_counts(self) -> dict[QueueStatus, int]:
        result = await self.session.execute(
            select(QueueItem.status, func.count(QueueItem.id)).group_by(QueueItem.status)
        )
        return {status: count for status, count in result.all()}

    async def _channel_counts(self) -> tuple[int, int]:
        result = await self.session.execute(
            select(
                func.count(TelegramChannel.id),
                func.coalesce(
                    func.sum(case((TelegramChannel.is_active.is_(True), 1), else_=0)),
                    0,
                ),
            )
        )
        total, active = result.one()
        return int(total), int(active)

    async def _recent_activity(self, *, limit: int) -> list[ActivityRecord]:
        products = select(
            literal("product").label("resource_type"),
            Product.id.label("resource_id"),
            Product.title.label("title"),
            cast(Product.status, String).label("status"),
            Product.created_at.label("occurred_at"),
        )
        queue_items = select(
            literal("queue").label("resource_type"),
            QueueItem.id.label("resource_id"),
            func.coalesce(QueueItem.title, literal("Queue item")).label("title"),
            cast(QueueItem.status, String).label("status"),
            QueueItem.created_at.label("occurred_at"),
        )
        activity = union_all(products, queue_items).subquery()
        result = await self.session.execute(
            select(activity).order_by(activity.c.occurred_at.desc()).limit(limit)
        )
        return [
            ActivityRecord(
                resource_type=row.resource_type,
                resource_id=row.resource_id,
                title=row.title,
                status=row.status.lower(),
                occurred_at=row.occurred_at,
            )
            for row in result
        ]
