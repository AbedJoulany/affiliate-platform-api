from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.enums import UserRole
from app.core.workspace import WORKSPACE_ID_HEADER, get_active_workspace
from app.models.user import User
from app.repositories.workspace import WorkspaceRepository
from app.schemas.campaign import CampaignCreate, CampaignRead, CampaignUpdate
from app.services.campaign import CampaignService
from app.services.exceptions import ForbiddenError, ServiceError

router = APIRouter()


@dataclass(frozen=True, slots=True)
class CampaignWorkspaceScope:
    """Validated workspace id for campaign routes.

    Non-admin callers go through ``get_active_workspace``. Admins may operate in
    any existing workspace without a membership row (Phase E global ADMIN),
    while still requiring a valid ``X-Workspace-Id``.
    """

    user: User
    workspace_id: UUID


async def get_campaign_workspace_scope(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_workspace_id: Annotated[str | None, Header(alias=WORKSPACE_ID_HEADER)] = None,
) -> CampaignWorkspaceScope:
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
        return CampaignWorkspaceScope(user=current_user, workspace_id=workspace.id)

    ctx = await get_active_workspace(current_user, db, x_workspace_id)
    return CampaignWorkspaceScope(user=ctx.user, workspace_id=ctx.workspace.id)


CampaignWorkspace = Annotated[CampaignWorkspaceScope, Depends(get_campaign_workspace_scope)]


@router.post("", response_model=CampaignRead, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    payload: CampaignCreate,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.ADVERTISER))],
    scope: CampaignWorkspace,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CampaignRead:
    try:
        return await CampaignService(db).create(current_user, payload, scope.workspace_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/active", response_model=list[CampaignRead])
async def list_active_campaigns(
    scope: CampaignWorkspace,
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
) -> list[CampaignRead]:
    return await CampaignService(db).list_active(
        scope.workspace_id,
        skip=skip,
        limit=limit,
    )


@router.get("/{campaign_id}", response_model=CampaignRead)
async def get_campaign(
    campaign_id: UUID,
    scope: CampaignWorkspace,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CampaignRead:
    try:
        return await CampaignService(db).get(campaign_id, scope.workspace_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("", response_model=list[CampaignRead])
async def list_campaigns(
    _: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    scope: CampaignWorkspace,
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
) -> list[CampaignRead]:
    return await CampaignService(db).list_all(
        scope.workspace_id,
        skip=skip,
        limit=limit,
    )


@router.patch("/{campaign_id}", response_model=CampaignRead)
async def update_campaign(
    campaign_id: UUID,
    payload: CampaignUpdate,
    scope: CampaignWorkspace,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CampaignRead:
    try:
        return await CampaignService(db).update(
            scope.user,
            campaign_id,
            payload,
            scope.workspace_id,
        )
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
