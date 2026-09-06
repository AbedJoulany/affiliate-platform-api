from typing import Annotated

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.database import get_db
from app.core.workspace import WORKSPACE_ID_HEADER
from app.models.user import User
from app.schemas.workspace_settings import WorkspaceSettingsPatch, WorkspaceSettingsRead
from app.services.workspace_settings import WorkspaceSettingsService

router = APIRouter()


@router.get("", response_model=WorkspaceSettingsRead)
async def get_workspace_settings(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_workspace_id: Annotated[str | None, Header(alias=WORKSPACE_ID_HEADER)] = None,
) -> WorkspaceSettingsRead:
    return await WorkspaceSettingsService(db).get(current_user, x_workspace_id)


@router.patch("", response_model=WorkspaceSettingsRead)
async def patch_workspace_settings(
    payload: WorkspaceSettingsPatch,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_workspace_id: Annotated[str | None, Header(alias=WORKSPACE_ID_HEADER)] = None,
) -> WorkspaceSettingsRead:
    return await WorkspaceSettingsService(db).patch(
        current_user,
        x_workspace_id,
        payload,
    )
