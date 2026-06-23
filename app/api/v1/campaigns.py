from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.campaign import CampaignCreate, CampaignRead, CampaignUpdate
from app.services.campaign import CampaignService
from app.services.exceptions import ServiceError

router = APIRouter()


@router.post("", response_model=CampaignRead, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    payload: CampaignCreate,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.ADVERTISER))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CampaignRead:
    try:
        return await CampaignService(db).create(current_user, payload)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/active", response_model=list[CampaignRead])
async def list_active_campaigns(
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
) -> list[CampaignRead]:
    return await CampaignService(db).list_active(skip=skip, limit=limit)


@router.get("/{campaign_id}", response_model=CampaignRead)
async def get_campaign(
    campaign_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CampaignRead:
    try:
        return await CampaignService(db).get(campaign_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("", response_model=list[CampaignRead])
async def list_campaigns(
    _: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
) -> list[CampaignRead]:
    return await CampaignService(db).list_all(skip=skip, limit=limit)


@router.patch("/{campaign_id}", response_model=CampaignRead)
async def update_campaign(
    campaign_id: UUID,
    payload: CampaignUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CampaignRead:
    try:
        return await CampaignService(db).update(current_user, campaign_id, payload)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
