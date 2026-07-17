from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.api.deps_aliexpress import AliExpressImportServiceDep
from app.auth.dependencies import CurrentUser
from app.core.database import get_db
from app.core.enums import UserRole
from app.models.user import User
from app.schemas.aliexpress import (
    AliExpressCategoryListResponse,
    AliExpressImportRequest,
    AliExpressImportResponse,
)
from app.services.aliexpress_categories import AliExpressCategoryService
from app.services.exceptions import ServiceError

router = APIRouter()


@router.get("/categories", response_model=AliExpressCategoryListResponse)
async def list_cached_categories(
    _: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AliExpressCategoryListResponse:
    return await AliExpressCategoryService(db).list_cached()


@router.post("/import", response_model=AliExpressImportResponse)
async def import_aliexpress_product(
    payload: AliExpressImportRequest,
    response: Response,
    _: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    import_service: AliExpressImportServiceDep,
) -> AliExpressImportResponse:
    try:
        result = await import_service.import_product(
            url=str(payload.url) if payload.url else None,
            product_id=payload.product_id,
        )
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    response.status_code = status.HTTP_201_CREATED if result.imported else status.HTTP_200_OK
    return result
