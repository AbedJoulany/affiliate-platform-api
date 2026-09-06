from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.enums import QueueStatus
from app.models.queue import QueueItem, QueuePublishAttempt
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

    async def get_by_id_in_workspace(
        self,
        queue_id: UUID,
        workspace_id: UUID,
    ) -> QueueItem | None:
        result = await self.session.execute(
            select(QueueItem).where(
                QueueItem.id == queue_id,
                QueueItem.workspace_id == workspace_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_with_relations_in_workspace(
        self,
        queue_id: UUID,
        workspace_id: UUID,
    ) -> QueueItem | None:
        result = await self.session.execute(
            select(QueueItem)
            .options(
                selectinload(QueueItem.channel),
                selectinload(QueueItem.product),
            )
            .where(
                QueueItem.id == queue_id,
                QueueItem.workspace_id == workspace_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_with_relations_for_update(self, queue_id: UUID) -> QueueItem | None:
        """Lock the queue row, then load relations for the claim transaction.

        The lock query selects only the primary key with ``FOR UPDATE`` so eager
        loads do not expand the lock into outer joins. Relations are loaded in a
        second query after the row lock is held.
        """
        locked = await self.session.execute(
            select(QueueItem.id).where(QueueItem.id == queue_id).with_for_update()
        )
        if locked.scalar_one_or_none() is None:
            return None
        return await self.get_with_relations(queue_id)

    async def list_items(
        self,
        workspace_id: UUID,
        *,
        status: QueueStatus | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[QueueItem], int]:
        filters = self._build_filters(status=status)
        filters.append(QueueItem.workspace_id == workspace_id)

        count_query = select(func.count()).select_from(QueueItem).where(*filters)
        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()

        items_query = (
            select(QueueItem)
            .where(*filters)
            .order_by(QueueItem.created_at.desc())
            .offset(skip)
            .limit(limit)
        )

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


class QueuePublishAttemptRepository(BaseRepository[QueuePublishAttempt]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, QueuePublishAttempt)

    async def create_attempt(self, attempt: QueuePublishAttempt) -> QueuePublishAttempt:
        return await self.create(attempt)

    async def list_attempts(self, queue_id: UUID) -> list[QueuePublishAttempt]:
        result = await self.session.execute(
            select(QueuePublishAttempt)
            .where(QueuePublishAttempt.queue_id == queue_id)
            .order_by(
                QueuePublishAttempt.attempt_number.desc(),
                QueuePublishAttempt.id.desc(),
            )
        )
        return list(result.scalars().all())

    async def latest_attempt(self, queue_id: UUID) -> QueuePublishAttempt | None:
        result = await self.session.execute(
            select(QueuePublishAttempt)
            .where(QueuePublishAttempt.queue_id == queue_id)
            .order_by(
                QueuePublishAttempt.attempt_number.desc(),
                QueuePublishAttempt.id.desc(),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def active_guard_lookup(
        self,
        queue_id: UUID,
        content_hash: str,
        *,
        now: datetime,
    ) -> QueuePublishAttempt | None:
        result = await self.session.execute(
            select(QueuePublishAttempt)
            .where(
                QueuePublishAttempt.queue_id == queue_id,
                QueuePublishAttempt.content_hash == content_hash,
                QueuePublishAttempt.status.in_(("started", "succeeded")),
                QueuePublishAttempt.idempotency_expires_at > now,
            )
            .order_by(
                QueuePublishAttempt.attempt_number.desc(),
                QueuePublishAttempt.id.desc(),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()
