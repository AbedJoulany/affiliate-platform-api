from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.enums import UserRole
from app.core.rate_limit import limit_conversions
from app.models.user import User
from app.schemas.conversion import ConversionCreate, ConversionRead, ConversionUpdate
from app.services.conversion import ConversionService
from app.services.exceptions import ServiceError

router = APIRouter()


@router.post(
    "",
    response_model=ConversionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limit_conversions)],
)
async def record_conversion(
    payload: ConversionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConversionRead:
    try:
        return await ConversionService(db).record_conversion(payload)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/me", response_model=list[ConversionRead])
async def list_my_conversions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
) -> list[ConversionRead]:
    try:
        return await ConversionService(db).list_for_affiliate(
            current_user,
            skip=skip,
            limit=limit,
        )
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("", response_model=list[ConversionRead])
async def list_all_conversions(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
) -> list[ConversionRead]:
    try:
        return await ConversionService(db).list_all(current_user, skip=skip, limit=limit)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.patch("/{conversion_id}", response_model=ConversionRead)
async def update_conversion_status(
    conversion_id: UUID,
    payload: ConversionUpdate,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConversionRead:
    try:
        return await ConversionService(db).update_status(current_user, conversion_id, payload)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
