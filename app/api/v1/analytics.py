from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import HttpWorkspaceId
from app.core.database import get_db
from app.schemas.analytics import AnalyticsCampaignFunnelResponse, AnalyticsOverviewResponse
from app.services.analytics import AnalyticsService

router = APIRouter()


@router.get("/overview", response_model=AnalyticsOverviewResponse)
async def get_analytics_overview(
    workspace_id: HttpWorkspaceId,
    db: Annotated[AsyncSession, Depends(get_db)],
    range_from: Annotated[datetime | None, Query(alias="from")] = None,
    range_to: Annotated[datetime | None, Query(alias="to")] = None,
) -> AnalyticsOverviewResponse:
    return await AnalyticsService(db).get_overview(
        workspace_id,
        range_from=range_from,
        range_to=range_to,
    )


@router.get(
    "/campaigns/{campaign_id}/funnel",
    response_model=AnalyticsCampaignFunnelResponse,
)
async def get_campaign_funnel(
    campaign_id: UUID,
    workspace_id: HttpWorkspaceId,
    db: Annotated[AsyncSession, Depends(get_db)],
    range_from: Annotated[datetime | None, Query(alias="from")] = None,
    range_to: Annotated[datetime | None, Query(alias="to")] = None,
) -> AnalyticsCampaignFunnelResponse:
    return await AnalyticsService(db).get_campaign_funnel(
        workspace_id,
        campaign_id,
        range_from=range_from,
        range_to=range_to,
    )
