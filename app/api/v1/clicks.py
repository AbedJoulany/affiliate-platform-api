from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.rate_limit import limit_clicks
from app.services.click import ClickService
from app.services.exceptions import ServiceError

router = APIRouter()


@router.get(
    "/{affiliate_campaign_id}",
    status_code=status.HTTP_302_FOUND,
    response_class=RedirectResponse,
    dependencies=[Depends(limit_clicks)],
)
async def track_click(
    affiliate_campaign_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RedirectResponse:
    """Public affiliate-link redirect. No JWT and no X-Workspace-Id."""
    try:
        _click, destination = await ClickService(db).record_public_click(
            affiliate_campaign_id
        )
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return RedirectResponse(url=destination, status_code=status.HTTP_302_FOUND)
