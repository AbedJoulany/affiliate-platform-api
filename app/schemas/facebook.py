from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.enums import FacebookPageValidationStatus
from app.schemas.common import PaginatedResponse, TimestampSchema


def _page_id(value: str) -> str:
    value = value.strip()
    if not value.isdigit():
        raise ValueError("Facebook Page ID must contain only digits")
    return value


class FacebookPageCreate(BaseModel):
    facebook_page_id: str = Field(min_length=1, max_length=64)
    access_token: str = Field(min_length=1, max_length=4096)
    token_expires_at: datetime | None = None

    @field_validator("facebook_page_id")
    @classmethod
    def validate_page_id(cls, value: str) -> str:
        return _page_id(value)

    @field_validator("access_token")
    @classmethod
    def validate_token(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Facebook access token is required")
        return value


class FacebookPageUpdate(BaseModel):
    access_token: str | None = Field(default=None, min_length=1, max_length=4096)
    token_expires_at: datetime | None = None
    is_active: bool | None = None

    @field_validator("access_token")
    @classmethod
    def validate_token(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Facebook access token cannot be empty")
        return value


class FacebookPageRead(TimestampSchema):
    id: UUID
    workspace_id: UUID
    facebook_page_id: str
    page_name: str
    token_expires_at: datetime | None
    is_active: bool
    validation_status: FacebookPageValidationStatus
    last_validated_at: datetime | None
    last_error: str | None
    has_access_token: bool


class FacebookPageListResponse(PaginatedResponse):
    items: list[FacebookPageRead]
