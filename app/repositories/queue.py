import hashlib
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.core.enums import QueueStatus
from app.models.queue import QueueItem, QueuePublishAttempt
from app.repositories.base import BaseRepository


@dataclass(frozen=True, slots=True)
class ProductPublishingHistory:
    queued_or_scheduled: frozenset[UUID]
    recently_published: frozenset[UUID]
    unresolved_ambiguous: frozenset[UUID]


class QueueRepository(BaseRepository[QueueItem]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, QueueItem)

    def _build_filters(self, *, status: QueueStatus | None = None) -> list:
        filters = []
        if status is not None:
            filters.append(QueueItem.status == status)
        return filters

    async def acquire_workspace_queue_reservation_lock(
        self,
        *,
        workspace_id: UUID,
    ) -> None:
        """Serialize publishable Queue reservations within a workspace.

        This lock is shared by manual creation/update and automation. Workspace
        scope intentionally covers product checks across different destinations;
        it is held only during the short database transaction, never AI/provider
        work. PostgreSQL releases it automatically on commit or rollback.
        """
        bind = self.session.get_bind()
        if bind.dialect.name != "postgresql":
            return

        scope = f"queue-workspace-reservation:{workspace_id}".encode()
        lock_key = int.from_bytes(
            hashlib.blake2b(scope, digest_size=8).digest(),
            byteorder="big",
            signed=True,
        )
        await self.session.execute(select(func.pg_advisory_xact_lock(lock_key)))

    async def acquire_destination_capacity_lock(
        self,
        *,
        workspace_id: UUID,
        provider: str,
        destination_id: UUID,
    ) -> None:
        """Serialize automation capacity allocation for one destination.

        PostgreSQL advisory transaction locks work across API processes and are
        released automatically on commit or rollback. SQLite has no equivalent
        primitive, so local SQLite tests continue without the cross-process
        guarantee that is verified by the PostgreSQL integration suite.
        """
        bind = self.session.get_bind()
        if bind.dialect.name != "postgresql":
            return

        scope = f"{workspace_id}:{provider}:{destination_id}".encode()
        lock_key = int.from_bytes(
            hashlib.blake2b(scope, digest_size=8).digest(),
            byteorder="big",
            signed=True,
        )
        await self.session.execute(select(func.pg_advisory_xact_lock(lock_key)))

    async def get_with_relations(self, queue_id: UUID) -> QueueItem | None:
        result = await self.session.execute(
            select(QueueItem)
            .options(
                selectinload(QueueItem.channel),
                selectinload(QueueItem.facebook_page),
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

    async def get_by_id_in_workspace_for_update(
        self,
        queue_id: UUID,
        workspace_id: UUID,
    ) -> QueueItem | None:
        """Lock a workspace-owned Queue row before a reservation-sensitive edit."""
        result = await self.session.execute(
            select(QueueItem)
            .where(
                QueueItem.id == queue_id,
                QueueItem.workspace_id == workspace_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
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
                selectinload(QueueItem.facebook_page),
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
                selectinload(QueueItem.facebook_page),
                selectinload(QueueItem.product),
            )
            .where(
                QueueItem.status == QueueStatus.SCHEDULED,
                QueueItem.scheduled_at <= due_before,
                ((QueueItem.provider == "telegram") & QueueItem.channel_id.is_not(None))
                | ((QueueItem.provider == "facebook") & QueueItem.facebook_page_id.is_not(None)),
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
                ((QueueItem.provider == "telegram") & QueueItem.channel_id.is_not(None))
                | ((QueueItem.provider == "facebook") & QueueItem.facebook_page_id.is_not(None)),
            )
            .order_by(QueueItem.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def product_publishing_history(
        self,
        workspace_id: UUID,
        product_ids: list[UUID],
        *,
        now: datetime,
        recent_window_start: datetime,
    ) -> ProductPublishingHistory:
        """Load bounded, workspace-scoped product exclusion sets.

        A later conclusive attempt resolves an earlier ambiguous attempt. A
        newer ``started`` attempt does not, so the product remains blocked.
        The queries operate only on the candidate IDs supplied by the bounded
        catalog query.
        """
        if not product_ids:
            return ProductPublishingHistory(frozenset(), frozenset(), frozenset())

        queued_result = await self.session.execute(
            select(QueueItem.product_id)
            .where(
                QueueItem.workspace_id == workspace_id,
                QueueItem.product_id.in_(product_ids),
                QueueItem.status.in_((QueueStatus.QUEUED, QueueStatus.SCHEDULED)),
            )
            .distinct()
        )

        successful_attempt = exists(
            select(QueuePublishAttempt.id).where(
                QueuePublishAttempt.queue_id == QueueItem.id,
                QueuePublishAttempt.status == "succeeded",
                QueuePublishAttempt.occurred_at >= recent_window_start,
                QueuePublishAttempt.occurred_at < now,
            )
        )
        published_result = await self.session.execute(
            select(QueueItem.product_id)
            .where(
                QueueItem.workspace_id == workspace_id,
                QueueItem.product_id.in_(product_ids),
                or_(
                    and_(
                        QueueItem.published_at.is_not(None),
                        QueueItem.published_at >= recent_window_start,
                        QueueItem.published_at < now,
                    ),
                    successful_attempt,
                ),
            )
            .distinct()
        )

        later_conclusive_attempt = aliased(QueuePublishAttempt)
        no_later_conclusive_attempt = ~exists(
            select(later_conclusive_attempt.id).where(
                later_conclusive_attempt.queue_id == QueuePublishAttempt.queue_id,
                later_conclusive_attempt.attempt_number
                > QueuePublishAttempt.attempt_number,
                later_conclusive_attempt.status.in_(("succeeded", "failed")),
            )
        )
        ambiguous_result = await self.session.execute(
            select(QueueItem.product_id)
            .join(
                QueuePublishAttempt,
                QueuePublishAttempt.queue_id == QueueItem.id,
            )
            .where(
                QueueItem.workspace_id == workspace_id,
                QueueItem.product_id.in_(product_ids),
                QueuePublishAttempt.status == "ambiguous",
                no_later_conclusive_attempt,
            )
            .distinct()
        )

        return ProductPublishingHistory(
            queued_or_scheduled=frozenset(queued_result.scalars().all()),
            recently_published=frozenset(published_result.scalars().all()),
            unresolved_ambiguous=frozenset(ambiguous_result.scalars().all()),
        )

    async def list_destination_publishing_timestamps(
        self,
        *,
        workspace_id: UUID,
        provider: str,
        destination_id: UUID,
        start_utc: datetime,
        end_utc: datetime,
    ) -> list[datetime]:
        """Return bounded scheduled/published timestamps for one destination."""
        destination_filter = (
            QueueItem.channel_id == destination_id
            if provider == "telegram"
            else QueueItem.facebook_page_id == destination_id
        )
        result = await self.session.execute(
            select(QueueItem.status, QueueItem.scheduled_at, QueueItem.published_at)
            .where(
                QueueItem.workspace_id == workspace_id,
                QueueItem.provider == provider,
                destination_filter,
                or_(
                    and_(
                        QueueItem.status == QueueStatus.SCHEDULED,
                        QueueItem.scheduled_at >= start_utc,
                        QueueItem.scheduled_at < end_utc,
                    ),
                    and_(
                        QueueItem.status == QueueStatus.PUBLISHED,
                        QueueItem.published_at >= start_utc,
                        QueueItem.published_at < end_utc,
                    ),
                ),
            )
        )
        timestamps: list[datetime] = []
        for status, scheduled_at, published_at in result.all():
            timestamp = (
                scheduled_at
                if status == QueueStatus.SCHEDULED
                else published_at
            )
            if timestamp is not None:
                timestamps.append(timestamp)
        return timestamps


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
