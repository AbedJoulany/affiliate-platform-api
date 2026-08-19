from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.enums import UserRole
from app.core.rate_limit import limit_conversions
from app.core.workspace import WORKSPACE_ID_HEADER, get_active_workspace
from app.models.user import User
from app.repositories.workspace import WorkspaceRepository
from app.schemas.conversion import ConversionCreate, ConversionRead, ConversionUpdate
from app.services.conversion import ConversionService
from app.services.exceptions import ForbiddenError, ServiceError

router = APIRouter()


async def get_conversion_workspace_id(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_workspace_id: Annotated[str | None, Header(alias=WORKSPACE_ID_HEADER)] = None,
) -> UUID:
    """Resolve the active workspace for conversion routes.

    Non-admins use Task 3 ``get_active_workspace``. Admins may name any existing
    workspace without a membership row, matching Task 4's global-admin pattern.
    """
    if current_user.role == UserRole.ADMIN:
        if x_workspace_id is None or not x_workspace_id.strip():
            raise ForbiddenError()
        try:
            workspace_id = UUID(x_workspace_id.strip())
        except ValueError as exc:
            raise ForbiddenError() from exc
        workspace = await WorkspaceRepository(db).get_by_id(workspace_id)
        if workspace is None:
            raise ForbiddenError()
        return workspace.id
    ctx = await get_active_workspace(current_user, db, x_workspace_id)
    return ctx.workspace.id


ConversionWorkspaceId = Annotated[UUID, Depends(get_conversion_workspace_id)]


@router.post(
    "",
    response_model=ConversionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(limit_conversions)],
)
async def record_conversion(
    payload: ConversionCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    workspace_id: ConversionWorkspaceId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConversionRead:
    try:
        return await ConversionService(db).record_conversion(
            current_user,
            payload,
            workspace_id,
        )
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/me", response_model=list[ConversionRead])
async def list_my_conversions(
    current_user: Annotated[User, Depends(get_current_user)],
    workspace_id: ConversionWorkspaceId,
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
) -> list[ConversionRead]:
    try:
        return await ConversionService(db).list_for_affiliate(
            current_user,
            workspace_id,
            skip=skip,
            limit=limit,
        )
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("", response_model=list[ConversionRead])
async def list_all_conversions(
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    workspace_id: ConversionWorkspaceId,
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
) -> list[ConversionRead]:
    try:
        return await ConversionService(db).list_all(
            current_user,
            workspace_id,
            skip=skip,
            limit=limit,
        )
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.patch("/{conversion_id}", response_model=ConversionRead)
async def update_conversion_status(
    conversion_id: UUID,
    payload: ConversionUpdate,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    workspace_id: ConversionWorkspaceId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ConversionRead:
    try:
        return await ConversionService(db).update_status(
            current_user,
            conversion_id,
            payload,
            workspace_id,
        )
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
