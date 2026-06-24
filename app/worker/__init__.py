from app.worker.celery_app import celery_app
from app.worker.tasks import publishing  # noqa: F401

__all__ = ["celery_app"]
