from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.affiliate import (
    AffiliateCampaignJoin,
    AffiliateCampaignRead,
    AffiliateCreate,
    AffiliateRead,
    AffiliateUpdate,
)
from app.services.affiliate import AffiliateService
from app.services.exceptions import ServiceError

router = APIRouter()


@router.get("/me", response_model=AffiliateRead)
async def get_my_affiliate_profile(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AffiliateRead:
    try:
        return await AffiliateService(db).get_my_profile(current_user)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("", response_model=AffiliateRead, status_code=status.HTTP_201_CREATED)
async def create_affiliate_profile(
    payload: AffiliateCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AffiliateRead:
    try:
        return await AffiliateService(db).create_profile(current_user, payload)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.patch("/{affiliate_id}", response_model=AffiliateRead)
async def update_affiliate_profile(
    affiliate_id: UUID,
    payload: AffiliateUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AffiliateRead:
    try:
        return await AffiliateService(db).update_profile(current_user, affiliate_id, payload)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/join-campaign", response_model=AffiliateCampaignRead, status_code=status.HTTP_201_CREATED)
async def join_campaign(
    payload: AffiliateCampaignJoin,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AffiliateCampaignRead:
    try:
        return await AffiliateService(db).join_campaign(current_user, payload.campaign_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("", response_model=list[AffiliateRead])
async def list_affiliates(
    _: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
) -> list[AffiliateRead]:
    return await AffiliateService(db).list_affiliates(skip=skip, limit=limit)
