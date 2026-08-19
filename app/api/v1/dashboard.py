from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import HttpWorkspaceId
from app.core.database import get_db
from app.schemas.dashboard import DashboardResponse
from app.services.dashboard import DashboardService

router = APIRouter()


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    workspace_id: HttpWorkspaceId,
    db: Annotated[AsyncSession, Depends(get_db)],
    activity_limit: int = Query(default=10, ge=1, le=50),
) -> DashboardResponse:
    return await DashboardService(db).get_dashboard(
        workspace_id,
        activity_limit=activity_limit,
    )
