from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.auth.models import User
from app.core.database import get_db
from app.core.workspace import WORKSPACE_ID_HEADER
from app.schemas.facebook import (
    FacebookPageCreate,
    FacebookPageListResponse,
    FacebookPageRead,
    FacebookPageUpdate,
)
from app.services.exceptions import ServiceError
from app.services.facebook_page import FacebookPageService

router = APIRouter()


def _handle(exc: ServiceError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/pages", response_model=FacebookPageListResponse)
async def list_pages(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_workspace_id: str | None = Header(default=None, alias=WORKSPACE_ID_HEADER),
) -> FacebookPageListResponse:
    try:
        return await FacebookPageService(db).list(current_user, x_workspace_id)
    except ServiceError as exc:
        raise _handle(exc) from exc


@router.post("/pages", response_model=FacebookPageRead, status_code=status.HTTP_201_CREATED)
async def create_page(
    payload: FacebookPageCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_workspace_id: str | None = Header(default=None, alias=WORKSPACE_ID_HEADER),
) -> FacebookPageRead:
    try:
        page = await FacebookPageService(db).create(current_user, x_workspace_id, payload)
        return FacebookPageService._to_read(page)
    except ServiceError as exc:
        raise _handle(exc) from exc


@router.post("/pages/{page_id}/validate", response_model=FacebookPageRead)
async def validate_page(
    page_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_workspace_id: str | None = Header(default=None, alias=WORKSPACE_ID_HEADER),
) -> FacebookPageRead:
    try:
        page = await FacebookPageService(db).validate(current_user, x_workspace_id, page_id)
        return FacebookPageService._to_read(page)
    except ServiceError as exc:
        raise _handle(exc) from exc


@router.patch("/pages/{page_id}", response_model=FacebookPageRead)
async def update_page(
    page_id: UUID,
    payload: FacebookPageUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_workspace_id: str | None = Header(default=None, alias=WORKSPACE_ID_HEADER),
) -> FacebookPageRead:
    try:
        page = await FacebookPageService(db).update(current_user, x_workspace_id, page_id, payload)
        return FacebookPageService._to_read(page)
    except ServiceError as exc:
        raise _handle(exc) from exc


@router.delete("/pages/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_page(
    page_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_workspace_id: str | None = Header(default=None, alias=WORKSPACE_ID_HEADER),
) -> None:
    try:
        await FacebookPageService(db).delete(current_user, x_workspace_id, page_id)
    except ServiceError as exc:
        raise _handle(exc) from exc
