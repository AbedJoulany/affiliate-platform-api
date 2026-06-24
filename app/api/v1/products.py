from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.core.database import get_db
from app.core.enums import ProductStatus, UserRole
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.product import ProductCreate, ProductListResponse, ProductRead, ProductUpdate
from app.services.exceptions import ServiceError
from app.services.product import ProductService

router = APIRouter()


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductRead:
    try:
        return await ProductService(db).create(current_user, payload)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("", response_model=ProductListResponse)
async def list_products(
    db: Annotated[AsyncSession, Depends(get_db)],
    title: str | None = Query(default=None, description="Search products by title"),
    status: ProductStatus | None = Query(default=None, description="Filter by product status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=200),
) -> ProductListResponse:
    return await ProductService(db).list_products(
        title=title,
        status=status,
        skip=skip,
        limit=limit,
    )


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(
    product_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductRead:
    try:
        return await ProductService(db).get(product_id)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.patch("/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: UUID,
    payload: ProductUpdate,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProductRead:
    try:
        return await ProductService(db).update(current_user, product_id, payload)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.delete("/{product_id}", response_model=MessageResponse)
async def delete_product(
    product_id: UUID,
    current_user: Annotated[User, Depends(require_roles(UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MessageResponse:
    try:
        await ProductService(db).delete(current_user, product_id)
        return MessageResponse(message="Product deleted successfully")
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
