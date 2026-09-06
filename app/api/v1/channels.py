from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import HttpWorkspaceId
from app.core.database import get_db
from app.models.channel import TelegramChannel
from app.schemas.channel import ChannelCreate, ChannelListResponse, ChannelRead, ChannelUpdate
from app.schemas.common import MessageResponse
from app.services.channel import ChannelService
from app.services.exceptions import ServiceError

router = APIRouter()


@router.post("", response_model=ChannelRead, status_code=status.HTTP_201_CREATED)
async def create_channel(
    payload: ChannelCreate,
    workspace_id: HttpWorkspaceId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TelegramChannel:
    try:
        return await ChannelService(db).create(payload, workspace_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("", response_model=ChannelListResponse)
async def list_channels(
    workspace_id: HttpWorkspaceId,
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
) -> ChannelListResponse:
    return await ChannelService(db).list_channels(
        workspace_id,
        skip=skip,
        limit=limit,
    )


@router.put("/{channel_id}", response_model=ChannelRead)
async def update_channel(
    channel_id: UUID,
    payload: ChannelUpdate,
    workspace_id: HttpWorkspaceId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TelegramChannel:
    try:
        return await ChannelService(db).update(channel_id, payload, workspace_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.delete("/{channel_id}", response_model=MessageResponse)
async def delete_channel(
    channel_id: UUID,
    workspace_id: HttpWorkspaceId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    try:
        await ChannelService(db).delete(channel_id, workspace_id)
        return MessageResponse(message="Channel deleted successfully")
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
