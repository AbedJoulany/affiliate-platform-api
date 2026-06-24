from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.core.enums import UserRole
from app.schemas.common import TimestampSchema


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    role: UserRole = UserRole.AFFILIATE


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRead(TimestampSchema):
    id: UUID
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
