from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.core.database import get_db
from app.schemas.ai_content import GenerateContentRequest, GenerateContentResponse
from app.services.ai_content import AIContentService
from app.services.exceptions import ServiceError

router = APIRouter()


@router.post("/generate", response_model=GenerateContentResponse, status_code=status.HTTP_200_OK)
async def generate_content(
    payload: GenerateContentRequest,
    _: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GenerateContentResponse:
    try:
        return await AIContentService(db).generate_marketing_content(
            product_id=payload.product_id,
            url=str(payload.url) if payload.url else None,
            provider=payload.provider,
            content_type=payload.content_type,
            tone=payload.tone,
            language=payload.language,
            length=payload.length,
            instruction_modifiers=payload.instruction_modifiers,
        )
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
