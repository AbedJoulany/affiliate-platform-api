from uuid import UUID

from app.core.config import get_settings
from app.core.database import get_async_session_maker
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


@celery_app.task(name="app.worker.tasks.publishing.process_publish_queue")
def process_publish_queue(batch_size: int | None = None) -> dict:
    return run_async(_process_publish_queue(batch_size))


@celery_app.task(name="app.worker.tasks.publishing.publish_queue_item")
def publish_queue_item_task(queue_id: str) -> dict:
    return run_async(_publish_single_queue_item(UUID(queue_id)))
