from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import AuthServiceDep, CurrentUser
from app.auth.models import User
from app.auth.schemas import (
    LogoutRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserLogin,
    UserProfileUpdate,
    UserRead,
    UserRegister,
)
from app.core.database import get_db
from app.core.rate_limit import limit_auth_login, limit_auth_refresh
from app.core.workspace import default_workspace_id_for_user
from app.services.exceptions import ServiceError

router = APIRouter()


def get_login_credentials(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> UserLogin:
    """Validate OAuth2 form username as EmailStr; invalid input is HTTP 422."""
    try:
        return UserLogin(email=form_data.username, password=form_data.password)
    except PydanticValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserRegister,
    auth_service: AuthServiceDep,
) -> User:
    try:
        return await auth_service.register(payload)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(limit_auth_login)],
)
async def login(
    credentials: Annotated[UserLogin, Depends(get_login_credentials)],
    auth_service: AuthServiceDep,
) -> TokenResponse:
    try:
        return await auth_service.login(credentials)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post(
    "/refresh",
    response_model=TokenResponse,
    dependencies=[Depends(limit_auth_refresh)],
)
async def refresh(
    payload: RefreshTokenRequest,
    auth_service: AuthServiceDep,
) -> TokenResponse:
    try:
        return await auth_service.refresh(payload.refresh_token)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: LogoutRequest,
    auth_service: AuthServiceDep,
) -> Response:
    try:
        await auth_service.logout(payload.refresh_token)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserRead)
async def get_current_user_profile(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserRead:
    default_workspace_id = await default_workspace_id_for_user(db, current_user.id)
    return UserRead.model_validate(current_user).model_copy(
        update={"default_workspace_id": default_workspace_id},
    )


@router.patch("/me", response_model=UserRead)
async def update_current_user_profile(
    payload: UserProfileUpdate,
    current_user: CurrentUser,
    auth_service: AuthServiceDep,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserRead:
    try:
        user = await auth_service.update_profile(current_user, payload)
    except ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    default_workspace_id = await default_workspace_id_for_user(db, user.id)
    return UserRead.model_validate(user).model_copy(
        update={"default_workspace_id": default_workspace_id},
    )
