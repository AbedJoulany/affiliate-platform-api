"""Shared API dependencies — auth dependencies are re-exported from app.auth."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, oauth2_scheme, require_roles
from app.core.database import get_db
from app.events.deps import get_event_publisher
from app.events.publisher import EventPublisher, NullEventPublisher
from app.services.queue import QueueService

__all__ = [
    "get_current_user",
    "get_queue_service",
    "oauth2_scheme",
    "require_roles",
]


def get_queue_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    events: Annotated[
        EventPublisher | NullEventPublisher, Depends(get_event_publisher)
    ],
) -> QueueService:
    """QueueService with the process EventPublisher (or Null outside lifespan)."""
    return QueueService(db, events=events)
