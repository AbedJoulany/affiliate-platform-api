from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import BotPermissionStatus, QueueStatus
from app.models.channel import TelegramChannel
from app.models.queue import QueueItem
from app.repositories.channel import ChannelRepository
from app.repositories.product import ProductRepository
from app.repositories.queue import QueueRepository
from app.schemas.queue import PublishQueueResponse, QueueCreate, QueueListResponse, QueueUpdate
from app.services.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.telegram.publisher import TelegramPublisher
from app.telegram.types import InlineUrlButton


class TelegramPublishingService:
    DEFAULT_BUTTON_TEXT = "اشتري الآن"

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.queue_repo = QueueRepository(session)
        self.publisher = TelegramPublisher()

    async def publish_queue_item(self, queue_id: UUID) -> PublishQueueResponse:
        item = await self.queue_repo.get_with_relations(queue_id)
        if not item:
            raise NotFoundError("Queue item not found")

        if item.status == QueueStatus.PUBLISHED:
            raise ConflictError("Queue item is already published")

        if not item.channel_id or not item.channel:
            raise ValidationError("Queue item must have a channel assigned before publishing")

        self._ensure_channel_can_publish(item.channel)

        chat_id = item.channel.telegram_channel_id
        image_url = self._resolve_image_url(item)
        button = self._resolve_button(item)

        result = await self.publisher.publish(
            chat_id=chat_id,
            text=item.content,
            image_url=image_url,
            button=button,
        )

        item.status = QueueStatus.PUBLISHED
        item.published_at = datetime.now(UTC)
        item.telegram_message_id = result.message_id
        await self.queue_repo.update(item)

        return PublishQueueResponse(
            queue_id=item.id,
            telegram_message_id=result.message_id,
            chat_id=result.chat_id,
            message_type=result.message_type,
            published_at=item.published_at,
        )

    async def publish_due_scheduled(self, *, limit: int = 50) -> list[PublishQueueResponse]:
        due_items = await self.queue_repo.list_scheduled_due(
            due_before=datetime.now(UTC),
            limit=limit,
        )
        return await self._publish_items(due_items)

    async def publish_queued_items(self, *, limit: int = 50) -> list[PublishQueueResponse]:
        queued_items = await self.queue_repo.list_queued_ready(limit=limit)
        return await self._publish_items(queued_items)

    async def _publish_items(self, items: list[QueueItem]) -> list[PublishQueueResponse]:
        results: list[PublishQueueResponse] = []
        for item in items:
            try:
                results.append(await self.publish_queue_item(item.id))
            except (ValidationError, ForbiddenError, ConflictError):
                continue
        return results

    def _ensure_channel_can_publish(self, channel: TelegramChannel) -> None:
        if not channel.is_active:
            raise ValidationError("Telegram channel is inactive")
        if channel.bot_permission_status not in {
            BotPermissionStatus.GRANTED,
            BotPermissionStatus.PARTIAL,
        }:
            raise ForbiddenError("Bot does not have permission to publish to this channel")
        if not channel.can_post_messages:
            raise ForbiddenError("Bot cannot post messages to this channel")

    def _resolve_image_url(self, item: QueueItem) -> str | None:
        if item.image_url:
            return item.image_url
        if item.product:
            return item.product.image_url
        return None

    def _resolve_button(self, item: QueueItem) -> InlineUrlButton | None:
        button_text = item.button_text
        button_url = item.button_url

        if item.product and not button_url:
            button_url = item.product.product_url
        if button_url and not button_text:
            button_text = self.DEFAULT_BUTTON_TEXT

        if button_text and button_url:
            return InlineUrlButton(text=button_text, url=str(button_url))
        return None


class QueueService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.queue_repo = QueueRepository(session)
        self.channel_repo = ChannelRepository(session)
        self.product_repo = ProductRepository(session)
        self.publishing_service = TelegramPublishingService(session)

    async def create(self, payload: QueueCreate) -> QueueItem:
        await self._validate_relations(payload.channel_id, payload.product_id)
        self._validate_status_scheduling(payload.status, payload.scheduled_at)

        item = QueueItem(
            title=payload.title,
            content=payload.content,
            status=payload.status,
            scheduled_at=payload.scheduled_at,
            channel_id=payload.channel_id,
            product_id=payload.product_id,
            image_url=str(payload.image_url) if payload.image_url else None,
            button_text=payload.button_text,
            button_url=str(payload.button_url) if payload.button_url else None,
        )
        if payload.status == QueueStatus.PUBLISHED:
            item.published_at = datetime.now(UTC)

        return await self.queue_repo.create(item)

    async def get(self, queue_id: UUID) -> QueueItem:
        item = await self.queue_repo.get_by_id(queue_id)
        if not item:
            raise NotFoundError("Queue item not found")
        return item

    async def list_items(
        self,
        *,
        status: QueueStatus | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> QueueListResponse:
        items, total = await self.queue_repo.list_items(
            status=status,
            skip=skip,
            limit=limit,
        )
        return QueueListResponse(items=items, total=total, skip=skip, limit=limit)

    async def update(self, queue_id: UUID, payload: QueueUpdate) -> QueueItem:
        item = await self.get(queue_id)
        update_data = payload.model_dump(exclude_unset=True)

        new_status = update_data.get("status", item.status)
        new_scheduled_at = update_data.get("scheduled_at", item.scheduled_at)

        if "channel_id" in update_data:
            await self._validate_channel(update_data["channel_id"])
        if "product_id" in update_data:
            await self._validate_product(update_data["product_id"])

        if new_status == QueueStatus.SCHEDULED and new_scheduled_at is None:
            raise ValidationError("scheduled_at is required when status is scheduled")

        self._validate_status_scheduling(new_status, new_scheduled_at)

        for url_field in ("image_url", "button_url"):
            if url_field in update_data and update_data[url_field] is not None:
                update_data[url_field] = str(update_data[url_field])

        for field, value in update_data.items():
            setattr(item, field, value)

        if "status" in update_data:
            if item.status == QueueStatus.SCHEDULED and item.scheduled_at is None:
                item.scheduled_at = new_scheduled_at
            elif item.status != QueueStatus.SCHEDULED and "scheduled_at" not in update_data:
                item.scheduled_at = None

            if item.status == QueueStatus.PUBLISHED:
                item.published_at = datetime.now(UTC)
            elif item.status != QueueStatus.PUBLISHED:
                item.published_at = None
                item.telegram_message_id = None

        return await self.queue_repo.update(item)

    async def delete(self, queue_id: UUID) -> None:
        item = await self.get(queue_id)
        await self.queue_repo.delete(item)

    async def publish(self, queue_id: UUID) -> PublishQueueResponse:
        return await self.publishing_service.publish_queue_item(queue_id)

    async def _validate_relations(
        self,
        channel_id: UUID | None,
        product_id: UUID | None,
    ) -> None:
        await self._validate_channel(channel_id)
        await self._validate_product(product_id)

    async def _validate_channel(self, channel_id: UUID | None) -> None:
        if channel_id is None:
            return
        channel = await self.channel_repo.get_by_id(channel_id)
        if not channel:
            raise NotFoundError("Channel not found")

    async def _validate_product(self, product_id: UUID | None) -> None:
        if product_id is None:
            return
        product = await self.product_repo.get_by_id(product_id)
        if not product:
            raise NotFoundError("Product not found")

    def _validate_status_scheduling(
        self,
        status: QueueStatus,
        scheduled_at: datetime | None,
    ) -> None:
        if status == QueueStatus.SCHEDULED:
            if scheduled_at is None:
                raise ValidationError("scheduled_at is required when status is scheduled")
            if scheduled_at.tzinfo is None:
                raise ValidationError("scheduled_at must include timezone information")
