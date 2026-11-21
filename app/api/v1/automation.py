from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import HttpWorkspaceId
from app.auth.dependencies import CurrentUser
from app.core.database import get_db
from app.schemas.automation_discovery import AutomationDiscoveryPreviewResponse
from app.schemas.automation_policy import AutomationPolicyPatch, AutomationPolicyRead
from app.services.automation_discovery import AutomationDiscoveryService
from app.services.automation_policy import AutomationPolicyService

router = APIRouter()


@router.post(
    "/discovery/preview",
    response_model=AutomationDiscoveryPreviewResponse,
)
async def preview_automation_discovery(
    current_user: CurrentUser,
    workspace_id: HttpWorkspaceId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AutomationDiscoveryPreviewResponse:
    return await AutomationDiscoveryService(db).preview(current_user, workspace_id)


@router.get("/config", response_model=AutomationPolicyRead)
async def get_automation_config(
    current_user: CurrentUser,
    workspace_id: HttpWorkspaceId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AutomationPolicyRead:
    return await AutomationPolicyService(db).get(current_user, workspace_id)


@router.patch("/config", response_model=AutomationPolicyRead)
async def patch_automation_config(
    payload: AutomationPolicyPatch,
    current_user: CurrentUser,
    workspace_id: HttpWorkspaceId,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AutomationPolicyRead:
    return await AutomationPolicyService(db).patch(current_user, workspace_id, payload)
