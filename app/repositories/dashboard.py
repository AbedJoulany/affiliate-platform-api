from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import String, and_, case, cast, distinct, func, literal, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
    BotPermissionStatus,
    FacebookPageValidationStatus,
    ProductStatus,
    QueueStatus,
)
from app.models.channel import TelegramChannel
from app.models.facebook_page import FacebookPage
from app.models.product import Product
from app.models.queue import QueueItem, QueuePublishAttempt
from app.models.workspace_settings import WorkspaceSettings


@dataclass(frozen=True)
class ActivityRecord:
    resource_type: str
    resource_id: UUID
    title: str
    status: str
    occurred_at: datetime


@dataclass(frozen=True)
class ProviderPublishingCounts:
    published: int
    failed: int


@dataclass(frozen=True)
class PublishingSummary:
    published_today: int
    failed_today: int
    ambiguous_unresolved: int
    by_provider: dict[str, ProviderPublishingCounts]


@dataclass(frozen=True)
class AttentionRecord:
    queue_id: UUID
    title: str
    provider: str
    issue: str
    error_code: str | None
    message: str | None
    occurred_at: datetime


@dataclass(frozen=True)
class TelegramDestinationReadiness:
    total: int
    active: int
    permission_granted: int


@dataclass(frozen=True)
class FacebookDestinationReadiness:
    total: int
    active: int
    validated: int
    publishing_permission_verified: bool


@dataclass(frozen=True)
class DestinationReadiness:
    telegram: TelegramDestinationReadiness
    facebook: FacebookDestinationReadiness


@dataclass(frozen=True)
class DashboardSnapshot:
    product_counts: dict[ProductStatus, int]
    queue_counts: dict[QueueStatus, int]
    channel_total: int
    active_channels: int
    recent_activity: list[ActivityRecord]
    publishing: PublishingSummary
    attention_items: list[AttentionRecord]
    destination_readiness: DestinationReadiness


class DashboardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_workspace_timezone(self, workspace_id: UUID) -> str | None:
        result = await self.session.execute(
            select(WorkspaceSettings.timezone).where(
                WorkspaceSettings.workspace_id == workspace_id
            )
        )
        return result.scalar_one_or_none()

    async def get_snapshot(
        self,
        workspace_id: UUID,
        *,
        activity_limit: int = 10,
        day_start_utc: datetime,
        day_end_utc: datetime,
    ) -> DashboardSnapshot:
        product_counts = await self._product_counts()
        queue_counts = await self._queue_counts(workspace_id)
        channel_total, active_channels = await self._channel_counts(workspace_id)
        recent_activity = await self._recent_activity(
            workspace_id,
            limit=activity_limit,
        )
        publishing = await self._publishing_summary(
            workspace_id,
            day_start_utc=day_start_utc,
            day_end_utc=day_end_utc,
        )
        attention_items = await self._attention_items(workspace_id)
        destination_readiness = await self._destination_readiness(workspace_id)
        return DashboardSnapshot(
            product_counts=product_counts,
            queue_counts=queue_counts,
            channel_total=channel_total,
            active_channels=active_channels,
            recent_activity=recent_activity,
            publishing=publishing,
            attention_items=attention_items,
            destination_readiness=destination_readiness,
        )

    async def _publishing_summary(
        self,
        workspace_id: UUID,
        *,
        day_start_utc: datetime,
        day_end_utc: datetime,
    ) -> PublishingSummary:
        published_result = await self.session.execute(
            select(QueueItem.provider, func.count(QueueItem.id))
            .where(
                QueueItem.workspace_id == workspace_id,
                QueueItem.status == QueueStatus.PUBLISHED,
                QueueItem.published_at >= day_start_utc,
                QueueItem.published_at < day_end_utc,
            )
            .group_by(QueueItem.provider)
        )
        published_by_provider = {
            provider: int(count) for provider, count in published_result.all()
        }

        failed_result = await self.session.execute(
            select(
                QueueItem.provider,
                func.count(distinct(QueueItem.id)),
            )
            .select_from(QueuePublishAttempt)
            .join(QueueItem, QueueItem.id == QueuePublishAttempt.queue_id)
            .where(
                QueueItem.workspace_id == workspace_id,
                QueueItem.status == QueueStatus.FAILED,
                QueuePublishAttempt.status == "failed",
                QueuePublishAttempt.occurred_at >= day_start_utc,
                QueuePublishAttempt.occurred_at < day_end_utc,
            )
            .group_by(QueueItem.provider)
        )
        failed_by_provider = {
            provider: int(count) for provider, count in failed_result.all()
        }
        failed_total_result = await self.session.execute(
            select(func.count(distinct(QueuePublishAttempt.queue_id)))
            .select_from(QueuePublishAttempt)
            .join(QueueItem, QueueItem.id == QueuePublishAttempt.queue_id)
            .where(
                QueueItem.workspace_id == workspace_id,
                QueuePublishAttempt.status == "failed",
                QueuePublishAttempt.occurred_at >= day_start_utc,
                QueuePublishAttempt.occurred_at < day_end_utc,
            )
        )
        failed_today = int(failed_total_result.scalar_one() or 0)

        latest_attempt_numbers = (
            select(
                QueuePublishAttempt.queue_id,
                func.max(QueuePublishAttempt.attempt_number).label("latest_attempt_number"),
            )
            .join(QueueItem, QueueItem.id == QueuePublishAttempt.queue_id)
            .where(QueueItem.workspace_id == workspace_id)
            .group_by(QueuePublishAttempt.queue_id)
            .subquery()
        )
        ambiguous_result = await self.session.execute(
            select(func.count(QueueItem.id))
            .join(
                QueuePublishAttempt,
                and_(
                    QueuePublishAttempt.queue_id == QueueItem.id,
                    QueuePublishAttempt.attempt_number
                    == latest_attempt_numbers.c.latest_attempt_number,
                ),
            )
            .where(
                QueueItem.workspace_id == workspace_id,
                QueueItem.status != QueueStatus.PUBLISHED,
                QueuePublishAttempt.status == "ambiguous",
            )
        )
        ambiguous_unresolved = int(ambiguous_result.scalar_one() or 0)

        provider_counts = {
            provider: ProviderPublishingCounts(
                published=published_by_provider.get(provider, 0),
                failed=failed_by_provider.get(provider, 0),
            )
            for provider in ("telegram", "facebook")
        }
        return PublishingSummary(
            published_today=sum(published_by_provider.values()),
            failed_today=failed_today,
            ambiguous_unresolved=ambiguous_unresolved,
            by_provider=provider_counts,
        )

    async def _attention_items(self, workspace_id: UUID) -> list[AttentionRecord]:
        latest_attempt_numbers = (
            select(
                QueuePublishAttempt.queue_id,
                func.max(QueuePublishAttempt.attempt_number).label("latest_attempt_number"),
            )
            .join(QueueItem, QueueItem.id == QueuePublishAttempt.queue_id)
            .where(QueueItem.workspace_id == workspace_id)
            .group_by(QueuePublishAttempt.queue_id)
            .subquery()
        )
        latest_attempt = (
            select(
                QueuePublishAttempt.queue_id.label("queue_id"),
                QueuePublishAttempt.status.label("status"),
                QueuePublishAttempt.error_code.label("error_code"),
                QueuePublishAttempt.occurred_at.label("occurred_at"),
            )
            .join(
                latest_attempt_numbers,
                and_(
                    QueuePublishAttempt.queue_id == latest_attempt_numbers.c.queue_id,
                    QueuePublishAttempt.attempt_number
                    == latest_attempt_numbers.c.latest_attempt_number,
                ),
            )
            .subquery()
        )
        issue = case(
            (latest_attempt.c.status == "ambiguous", literal("ambiguous")),
            else_=literal("failed"),
        ).label("issue")
        occurred_at = case(
            (
                latest_attempt.c.status.in_(["failed", "ambiguous"]),
                latest_attempt.c.occurred_at,
            ),
            else_=QueueItem.updated_at,
        ).label("occurred_at")
        result = await self.session.execute(
            select(
                QueueItem.id,
                func.coalesce(QueueItem.title, literal("Queue item")).label("title"),
                QueueItem.provider,
                issue,
                latest_attempt.c.error_code,
                occurred_at,
            )
            .outerjoin(latest_attempt, latest_attempt.c.queue_id == QueueItem.id)
            .where(
                QueueItem.workspace_id == workspace_id,
                (
                    (QueueItem.status == QueueStatus.FAILED)
                    | (
                        (QueueItem.status != QueueStatus.PUBLISHED)
                        & (latest_attempt.c.status == "ambiguous")
                    )
                ),
            )
            .order_by(occurred_at.desc(), QueueItem.id.asc())
            .limit(10)
        )
        return [
            AttentionRecord(
                queue_id=row.id,
                title=row.title,
                provider=row.provider,
                issue=row.issue,
                error_code=row.error_code,
                message=None,
                occurred_at=row.occurred_at,
            )
            for row in result
        ]

    async def _destination_readiness(self, workspace_id: UUID) -> DestinationReadiness:
        telegram_result = await self.session.execute(
            select(
                func.count(TelegramChannel.id),
                func.coalesce(
                    func.sum(case((TelegramChannel.is_active.is_(True), 1), else_=0)),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                TelegramChannel.is_active.is_(True)
                                & TelegramChannel.can_post_messages.is_(True)
                                & TelegramChannel.bot_permission_status.in_(
                                    [
                                        BotPermissionStatus.GRANTED,
                                        BotPermissionStatus.PARTIAL,
                                    ]
                                ),
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ),
            ).where(TelegramChannel.workspace_id == workspace_id)
        )
        telegram_total, telegram_active, telegram_permission_granted = telegram_result.one()

        facebook_result = await self.session.execute(
            select(
                func.count(FacebookPage.id),
                func.coalesce(
                    func.sum(case((FacebookPage.is_active.is_(True), 1), else_=0)),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                FacebookPage.is_active.is_(True)
                                & (
                                    FacebookPage.validation_status
                                    == FacebookPageValidationStatus.VALID
                                ),
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ),
            ).where(FacebookPage.workspace_id == workspace_id)
        )
        facebook_total, facebook_active, facebook_validated = facebook_result.one()
        return DestinationReadiness(
            telegram=TelegramDestinationReadiness(
                total=int(telegram_total),
                active=int(telegram_active),
                permission_granted=int(telegram_permission_granted),
            ),
            facebook=FacebookDestinationReadiness(
                total=int(facebook_total),
                active=int(facebook_active),
                validated=int(facebook_validated),
                publishing_permission_verified=False,
            ),
        )

    async def _product_counts(self) -> dict[ProductStatus, int]:
        result = await self.session.execute(
            select(Product.status, func.count(Product.id)).group_by(Product.status)
        )
        return {status: count for status, count in result.all()}

    async def _queue_counts(self, workspace_id: UUID) -> dict[QueueStatus, int]:
        result = await self.session.execute(
            select(QueueItem.status, func.count(QueueItem.id))
            .where(QueueItem.workspace_id == workspace_id)
            .group_by(QueueItem.status)
        )
        return {status: count for status, count in result.all()}

    async def _channel_counts(self, workspace_id: UUID) -> tuple[int, int]:
        result = await self.session.execute(
            select(
                func.count(TelegramChannel.id),
                func.coalesce(
                    func.sum(case((TelegramChannel.is_active.is_(True), 1), else_=0)),
                    0,
                ),
            ).where(TelegramChannel.workspace_id == workspace_id)
        )
        total, active = result.one()
        return int(total), int(active)

    async def _recent_activity(
        self,
        workspace_id: UUID,
        *,
        limit: int,
    ) -> list[ActivityRecord]:
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
        ).where(QueueItem.workspace_id == workspace_id)
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
