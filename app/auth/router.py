from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.auth.dependencies import AuthServiceDep, CurrentUser
from app.auth.models import User
from app.auth.schemas import (
    LogoutRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserLogin,
    UserRead,
    UserRegister,
)
from app.core.rate_limit import limit_auth_login, limit_auth_refresh
from app.services.exceptions import ServiceError

router = APIRouter()


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
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    auth_service: AuthServiceDep,
) -> TokenResponse:
    try:
        return await auth_service.login(
            UserLogin(email=form_data.username, password=form_data.password)
        )
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
async def get_current_user_profile(current_user: CurrentUser) -> User:
    return current_user
