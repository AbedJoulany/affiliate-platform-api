from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import QueueStatus
from app.models.queue import QueueItem
from app.repositories.base import BaseRepository


class QueueRepository(BaseRepository[QueueItem]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, QueueItem)

    def _build_filters(self, *, status: QueueStatus | None = None) -> list:
        filters = []
        if status is not None:
            filters.append(QueueItem.status == status)
        return filters

    async def get_with_relations(self, queue_id: UUID) -> QueueItem | None:
        result = await self.session.execute(
            select(QueueItem)
            .options(
                selectinload(QueueItem.channel),
                selectinload(QueueItem.product),
            )
            .where(QueueItem.id == queue_id)
        )
        return result.scalar_one_or_none()

    async def list_items(
        self,
        *,
        status: QueueStatus | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[QueueItem], int]:
        filters = self._build_filters(status=status)

        count_query = select(func.count()).select_from(QueueItem)
        if filters:
            count_query = count_query.where(*filters)
        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()

        items_query = select(QueueItem)
        if filters:
            items_query = items_query.where(*filters)
        items_query = items_query.order_by(QueueItem.created_at.desc()).offset(skip).limit(limit)

        result = await self.session.execute(items_query)
        return list(result.scalars().all()), total

    async def list_scheduled_due(
        self,
        *,
        due_before,
        limit: int = 100,
    ) -> list[QueueItem]:
        result = await self.session.execute(
            select(QueueItem)
            .options(
                selectinload(QueueItem.channel),
                selectinload(QueueItem.product),
            )
            .where(
                QueueItem.status == QueueStatus.SCHEDULED,
                QueueItem.scheduled_at <= due_before,
                QueueItem.channel_id.is_not(None),
            )
            .order_by(QueueItem.scheduled_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_queued_ready(self, *, limit: int = 100) -> list[QueueItem]:
        result = await self.session.execute(
            select(QueueItem)
            .options(
                selectinload(QueueItem.channel),
                selectinload(QueueItem.product),
            )
            .where(
                QueueItem.status == QueueStatus.QUEUED,
                QueueItem.channel_id.is_not(None),
            )
            .order_by(QueueItem.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())
