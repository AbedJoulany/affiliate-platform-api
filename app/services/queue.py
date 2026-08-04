import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import BotPermissionStatus, QueueStatus
from app.models.channel import TelegramChannel
from app.models.queue import QueueItem, QueuePublishAttempt
from app.repositories.channel import ChannelRepository
from app.repositories.product import ProductRepository
from app.repositories.queue import QueuePublishAttemptRepository, QueueRepository
from app.schemas.queue import (
    PublishQueueResponse,
    QueueCreate,
    QueueListResponse,
    QueuePublishAttemptListResponse,
    QueuePublishAttemptRead,
    QueueRead,
    QueueUpdate,
)
from app.services.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ServiceError,
    TelegramPublishError,
    ValidationError,
)
from app.telegram.publisher import TelegramPublisher
from app.telegram.types import InlineUrlButton, TelegramPublishResult

IDEMPOTENCY_WINDOW = timedelta(hours=24)
# Terminal failure category after all retry paths are exhausted (or the error is
# not Celery-retryable). QueueItem.status is never changed for this outcome.
DEAD_LETTER_ERROR_CODE = "dead_letter"


@dataclass(frozen=True)
class _PublishSnapshot:
    """Outbound Telegram payload captured under the claim lock."""

    chat_id: str | None
    text: str
    image_url: str | None
    button: InlineUrlButton | None
    message_type: str
    parse_mode: str | None
    content_hash: str


@dataclass(frozen=True)
class _PublishClaim:
    item: QueueItem
    attempt: QueuePublishAttempt
    snapshot: _PublishSnapshot


class TelegramPublishingService:
    DEFAULT_BUTTON_TEXT = "اشتري الآن"

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.queue_repo = QueueRepository(session)
        self.attempt_repo = QueuePublishAttemptRepository(session)
        self.publisher = TelegramPublisher()

    async def publish_queue_item(
        self,
        queue_id: UUID,
        *,
        mark_transport_failure_terminal: bool = False,
    ) -> PublishQueueResponse:
        """Publish through the shared claim/idempotency guard.

        Manual API publish, scheduled/queued Celery batch work, and Celery
        autoretry all enter here, so they share the same lock and guard rules.

        ``mark_transport_failure_terminal`` is set by Celery callers on the final
        task execution (retries exhausted) and by the manual API path (no Celery
        retries). Non-``TelegramPublishError`` failures are always terminal.
        Terminal failures are persisted as dead-letter attempts; QueueItem.status
        is never set to a failure value.
        """
        claim = await self._claim_publish(queue_id)
        item = claim.item
        attempt = claim.attempt
        snapshot = claim.snapshot

        try:
            if item.status == QueueStatus.PUBLISHED:
                raise ConflictError("Queue item is already published")

            if not item.channel_id or not item.channel or snapshot.chat_id is None:
                raise ValidationError("Queue item must have a channel assigned before publishing")

            self._ensure_channel_can_publish(item.channel)

            # Use only the locked snapshot — do not re-read mutable relations.
            result = await self.publisher.publish(
                chat_id=snapshot.chat_id,
                text=snapshot.text,
                image_url=snapshot.image_url,
                button=snapshot.button,
                parse_mode=snapshot.parse_mode,
            )

            await self._mark_attempt_succeeded(attempt, result)

            item.status = QueueStatus.PUBLISHED
            item.published_at = datetime.now(UTC)
            item.telegram_message_id = result.message_id
            await self.queue_repo.update(item)
            # Commit success before returning so a later sibling failure in a
            # Celery batch cannot roll back a Telegram message that already sent.
            await self.session.commit()

            return PublishQueueResponse(
                queue_id=item.id,
                telegram_message_id=result.message_id,
                chat_id=result.chat_id,
                message_type=result.message_type,
                published_at=item.published_at,
            )
        except Exception as exc:
            # Celery autoretries only TelegramPublishError. All other failures are
            # terminal immediately. Transport failures become terminal when the
            # caller reports that Celery (or the manual path) has no retries left.
            # Non-retryable Telegram 4xx (except 429) are also terminal so the
            # beat loop does not recreate failed attempts forever.
            terminal = (
                mark_transport_failure_terminal
                or not isinstance(exc, TelegramPublishError)
                or self._is_non_retryable_telegram_error(exc)
            )
            await self._mark_attempt_failed(attempt, exc, terminal=terminal)
            raise

    async def publish_due_scheduled(
        self,
        *,
        limit: int = 50,
        mark_transport_failure_terminal: bool = False,
    ) -> list[PublishQueueResponse]:
        due_items = await self.queue_repo.list_scheduled_due(
            due_before=datetime.now(UTC),
            limit=limit,
        )
        return await self._publish_items(
            due_items,
            mark_transport_failure_terminal=mark_transport_failure_terminal,
        )

    async def publish_queued_items(
        self,
        *,
        limit: int = 50,
        mark_transport_failure_terminal: bool = False,
    ) -> list[PublishQueueResponse]:
        queued_items = await self.queue_repo.list_queued_ready(limit=limit)
        return await self._publish_items(
            queued_items,
            mark_transport_failure_terminal=mark_transport_failure_terminal,
        )

    async def _publish_items(
        self,
        items: list[QueueItem],
        *,
        mark_transport_failure_terminal: bool = False,
    ) -> list[PublishQueueResponse]:
        results: list[PublishQueueResponse] = []
        for item in items:
            try:
                results.append(
                    await self.publish_queue_item(
                        item.id,
                        mark_transport_failure_terminal=mark_transport_failure_terminal,
                    )
                )
            except (ValidationError, ForbiddenError, ConflictError, TelegramPublishError):
                # Persist-and-continue: one item's failure must not block the rest
                # of the due/queued batch for this beat tick. Attempt rows (and
                # dead-letter markers) are written inside publish_queue_item.
                continue
        return results

    async def _claim_publish(self, queue_id: UUID) -> _PublishClaim:
        """Lock the queue item, apply the idempotency guard, and claim a started attempt.

        Suppressed publishes raise ``ConflictError`` without inserting an attempt row.
        On success, the started attempt is committed so the row lock is released before
        any Telegram network I/O.
        """
        item = await self.queue_repo.get_with_relations_for_update(queue_id)
        if not item:
            raise NotFoundError("Queue item not found")

        now = datetime.now(UTC)
        snapshot = self._build_publish_snapshot(item)

        blocking = await self.attempt_repo.active_guard_lookup(
            item.id,
            snapshot.content_hash,
            now=now,
        )
        if blocking is not None:
            if blocking.status == "succeeded":
                # Heal status drift: Telegram already accepted the message but the
                # queue row never reached published (e.g. batch rollback). Keep the
                # idempotency suppress, but surface the true published state.
                if item.status != QueueStatus.PUBLISHED:
                    item.status = QueueStatus.PUBLISHED
                    item.published_at = item.published_at or blocking.occurred_at
                    item.telegram_message_id = (
                        item.telegram_message_id or blocking.provider_message_id
                    )
                    await self.queue_repo.update(item)
                    await self.session.commit()
                raise ConflictError(
                    "Publish already completed for this content; edit content to republish "
                    "or wait for the idempotency window to expire"
                )
            raise ConflictError(
                "Publish already in progress for this content; wait for the in-flight "
                "attempt to finish or for the idempotency window to expire"
            )

        latest = await self.attempt_repo.latest_attempt(item.id)
        attempt_number = 1 if latest is None else latest.attempt_number + 1
        attempt = QueuePublishAttempt(
            queue_id=item.id,
            attempt_number=attempt_number,
            provider="telegram",
            status="started",
            content_hash=snapshot.content_hash,
            idempotency_expires_at=now + IDEMPOTENCY_WINDOW,
            occurred_at=now,
        )
        attempt = await self.attempt_repo.create_attempt(attempt)
        # Commit releases the QueueItem row lock and makes the started marker durable
        # before Telegram is contacted.
        await self.session.commit()
        return _PublishClaim(item=item, attempt=attempt, snapshot=snapshot)

    def _build_publish_snapshot(self, item: QueueItem) -> _PublishSnapshot:
        image_url = self._resolve_image_url(item)
        button = self._resolve_button(item)
        chat_id = item.channel.telegram_channel_id if item.channel else None
        message_type = "photo" if image_url else "text"
        parse_mode = None
        content_hash = self._compute_content_hash(
            chat_id=chat_id,
            text=item.content,
            image_url=image_url,
            button=button,
            message_type=message_type,
            parse_mode=parse_mode,
        )
        return _PublishSnapshot(
            chat_id=chat_id,
            text=item.content,
            image_url=image_url,
            button=button,
            message_type=message_type,
            parse_mode=parse_mode,
            content_hash=content_hash,
        )

    async def _mark_attempt_succeeded(
        self,
        attempt: QueuePublishAttempt,
        result: TelegramPublishResult,
    ) -> QueuePublishAttempt:
        attempt.status = "succeeded"
        attempt.provider_chat_id = result.chat_id
        attempt.provider_message_id = result.message_id
        attempt.error_code = None
        attempt.error_message = None
        return await self.attempt_repo.update(attempt)

    async def _mark_attempt_failed(
        self,
        attempt: QueuePublishAttempt,
        exc: BaseException,
        *,
        terminal: bool = False,
    ) -> QueuePublishAttempt:
        """Persist a failed attempt. Never modifies QueueItem.status.

        When ``terminal`` is true (retries exhausted or non-retryable error), the
        attempt is marked with ``error_code=dead_letter`` so operators can filter
        "needs attention" from attempt history without a fake QueueStatus value.
        """
        underlying_code = self._error_code_for(exc)
        underlying_message = self._error_message_for(exc)
        attempt.status = "failed"
        if terminal:
            attempt.error_code = DEAD_LETTER_ERROR_CODE
            attempt.error_message = f"{underlying_code}: {underlying_message}"
        else:
            attempt.error_code = underlying_code
            attempt.error_message = underlying_message
        attempt.provider_chat_id = None
        attempt.provider_message_id = None
        attempt = await self.attempt_repo.update(attempt)
        # Persist the failure before the exception propagates and triggers rollback.
        await self.session.commit()
        return attempt

    def _compute_content_hash(
        self,
        *,
        chat_id: str | None,
        text: str,
        image_url: str | None,
        button: InlineUrlButton | None,
        message_type: str,
        parse_mode: str | None,
    ) -> str:
        payload = {
            "button_text": button.text if button else None,
            "button_url": button.url if button else None,
            "chat_id": chat_id,
            "image_url": image_url,
            "message_type": message_type,
            "parse_mode": parse_mode,
            "provider": "telegram",
            "text": text,
        }
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def _error_code_for(self, exc: BaseException) -> str:
        if isinstance(exc, ValidationError):
            return "validation_error"
        if isinstance(exc, ForbiddenError):
            return "forbidden_error"
        if isinstance(exc, ConflictError):
            return "conflict_error"
        if isinstance(exc, TelegramPublishError):
            if exc.http_status == 429 or exc.telegram_error_code == 429:
                return "telegram_429"
            if exc.telegram_error_code is not None:
                return f"telegram_{exc.telegram_error_code}"
            return "transport_error"
        if isinstance(exc, ServiceError):
            return "service_error"
        return "unexpected_error"

    def _is_non_retryable_telegram_error(self, exc: TelegramPublishError) -> bool:
        """True for permanent Telegram client failures that must not be beat-retried."""
        if exc.http_status == 429 or exc.telegram_error_code == 429:
            return False
        if exc.http_status is not None and 400 <= exc.http_status < 500:
            return True
        if isinstance(exc.telegram_error_code, int) and 400 <= exc.telegram_error_code < 500:
            return True
        return False

    def _error_message_for(self, exc: BaseException) -> str:
        if isinstance(exc, ServiceError):
            return exc.message
        return str(exc) or exc.__class__.__name__

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
        self.attempt_repo = QueuePublishAttemptRepository(session)
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

    async def get_read(self, queue_id: UUID) -> QueueRead:
        """Return a queue item with backend-owned attempt summary fields populated."""
        item = await self.get(queue_id)
        return await self._to_queue_read(item)

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
        # List responses keep attempt summary defaults (None/0) for compatibility and
        # to avoid N+1 lookups; clients use GET /queues/{id}/attempts for history.
        return QueueListResponse(items=items, total=total, skip=skip, limit=limit)

    async def list_publish_attempts(self, queue_id: UUID) -> QueuePublishAttemptListResponse:
        await self.get(queue_id)
        attempts = await self.attempt_repo.list_attempts(queue_id)
        return QueuePublishAttemptListResponse(
            queue_id=queue_id,
            items=[QueuePublishAttemptRead.model_validate(attempt) for attempt in attempts],
            total=len(attempts),
        )

    async def _to_queue_read(self, item: QueueItem) -> QueueRead:
        latest = await self.attempt_repo.latest_attempt(item.id)
        last_attempt = (
            QueuePublishAttemptRead.model_validate(latest) if latest is not None else None
        )
        failure_reason = None
        retry_count = 0
        if latest is not None:
            retry_count = latest.attempt_number
            if latest.status == "failed":
                failure_reason = latest.error_message
        return QueueRead.model_validate(item).model_copy(
            update={
                "last_attempt": last_attempt,
                "failure_reason": failure_reason,
                "retry_count": retry_count,
            }
        )

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
        # Manual publish has no Celery autoretry, so transport failures are terminal.
        return await self.publishing_service.publish_queue_item(
            queue_id,
            mark_transport_failure_terminal=True,
        )

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
