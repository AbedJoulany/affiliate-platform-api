from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.database import get_db
from app.core.enums import QueueStatus
from app.models.queue import QueueItem
from app.schemas.common import MessageResponse
from app.schemas.queue import (
    PublishQueueResponse,
    QueueCreate,
    QueueListResponse,
    QueuePublishAttemptListResponse,
    QueueRead,
    QueueUpdate,
)
from app.services.exceptions import ServiceError
from app.services.queue import QueueService

router = APIRouter()


@router.post("", response_model=QueueRead, status_code=status.HTTP_201_CREATED)
async def create_queue_item(
    payload: QueueCreate,
    _: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> QueueItem:
    try:
        return await QueueService(db).create(payload)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("", response_model=QueueListResponse)
async def list_queue_items(
    _: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    status: QueueStatus | None = Query(default=None, description="Filter by queue status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
) -> QueueListResponse:
    return await QueueService(db).list_items(status=status, skip=skip, limit=limit)


@router.get("/{queue_id}/attempts", response_model=QueuePublishAttemptListResponse)
async def list_queue_publish_attempts(
    queue_id: UUID,
    _: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> QueuePublishAttemptListResponse:
    """Return Telegram publish attempt history for a queue item, newest first.

    Attempt ``status`` values are attempt-scoped (started/succeeded/failed) and are
    not QueueStatus values. Idempotency-suppressed publishes do not create attempt
    rows; those are surfaced as HTTP 409 from ``POST /queues/{id}/publish``.
    """
    try:
        return await QueueService(db).list_publish_attempts(queue_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/{queue_id}", response_model=QueueRead)
async def get_queue_item(
    queue_id: UUID,
    _: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> QueueRead:
    try:
        return await QueueService(db).get_read(queue_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.patch("/{queue_id}", response_model=QueueRead)
async def update_queue_item(
    queue_id: UUID,
    payload: QueueUpdate,
    _: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> QueueItem:
    try:
        return await QueueService(db).update(queue_id, payload)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/{queue_id}/publish", response_model=PublishQueueResponse)
async def publish_queue_item(
    queue_id: UUID,
    _: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PublishQueueResponse:
    """Publish a queue item to Telegram.

    Idempotency-guard suppressions and other conflicts raise HTTP 409 with
    ``detail`` set to the ConflictError message. No attempt row is created when
    the guard suppresses a duplicate publish.
    """
    try:
        return await QueueService(db).publish(queue_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.delete("/{queue_id}", response_model=MessageResponse)
async def delete_queue_item(
    queue_id: UUID,
    _: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    try:
        await QueueService(db).delete(queue_id)
        return MessageResponse(message="Queue item deleted successfully")
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
