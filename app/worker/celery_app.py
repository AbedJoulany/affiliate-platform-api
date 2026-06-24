from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "affiliate_platform",
    broker=settings.broker_url,
    backend=settings.result_backend_url,
    include=["app.worker.tasks.publishing"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "process-publish-queue": {
            "task": "app.worker.tasks.publishing.process_publish_queue",
            "schedule": float(settings.celery_publish_interval_seconds),
        },
    },
)
