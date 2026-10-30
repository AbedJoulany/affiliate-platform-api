from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.database import get_db
from app.schemas.recommendations import RecommendationQuery, RecommendationResponse
from app.services.recommendations import RecommendationService

router = APIRouter()


@router.get("/recommendations", response_model=RecommendationResponse)
async def recommend_products(
    query: Annotated[RecommendationQuery, Depends()],
    _current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RecommendationResponse:
    return await RecommendationService(db).recommend(query)
