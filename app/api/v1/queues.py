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


@router.get("/{queue_id}", response_model=QueueRead)
async def get_queue_item(
    queue_id: UUID,
    _: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> QueueItem:
    try:
        return await QueueService(db).get(queue_id)
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
