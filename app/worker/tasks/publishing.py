from uuid import UUID

from app.core.config import get_settings
from app.core.database import get_async_session_maker
from app.services.exceptions import TelegramPublishError
from app.services.queue import TelegramPublishingService
from app.worker.async_utils import run_async
from app.worker.celery_app import celery_app

settings = get_settings()


async def _process_publish_queue(batch_size: int | None = None) -> dict:
    limit = batch_size or settings.celery_publish_batch_size
    session_maker = get_async_session_maker()

    async with session_maker() as session:
        service = TelegramPublishingService(session)
        scheduled_results = await service.publish_due_scheduled(limit=limit)
        queued_results = await service.publish_queued_items(limit=limit)
        await session.commit()

    return {
        "scheduled_published": len(scheduled_results),
        "queued_published": len(queued_results),
        "published_queue_ids": [
            str(result.queue_id)
            for result in (*scheduled_results, *queued_results)
        ],
    }


async def _publish_single_queue_item(queue_id: UUID) -> dict:
    session_maker = get_async_session_maker()

    async with session_maker() as session:
        service = TelegramPublishingService(session)
        result = await service.publish_queue_item(queue_id)
        await session.commit()

    return result.model_dump(mode="json")


# Retry semantics: max_retries=3 means 1 initial attempt + up to 3 retries
# (at most 4 task executions), matching TELEGRAM_MAX_RETRIES in the publisher.
#
# Duplicate-send protection: Celery autoretry re-enters
# TelegramPublishingService.publish_queue_item, which applies the shared
# claim/idempotency guard (row lock + active_guard_lookup) before contacting
# Telegram. An unexpired started/succeeded attempt for the same content hash
# suppresses the retry without creating a new attempt row.
@celery_app.task(
    name="app.worker.tasks.publishing.process_publish_queue",
    autoretry_for=(TelegramPublishError,),
    max_retries=3,
    retry_backoff=True,
    retry_jitter=True,
)
def process_publish_queue(batch_size: int | None = None) -> dict:
    return run_async(_process_publish_queue(batch_size))


@celery_app.task(
    name="app.worker.tasks.publishing.publish_queue_item",
    autoretry_for=(TelegramPublishError,),
    max_retries=3,
    retry_backoff=True,
    retry_jitter=True,
)
def publish_queue_item_task(queue_id: str) -> dict:
    return run_async(_publish_single_queue_item(UUID(queue_id)))
