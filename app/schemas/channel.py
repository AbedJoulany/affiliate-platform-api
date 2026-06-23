from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.enums import BotPermissionStatus
from app.schemas.common import PaginatedResponse, TimestampSchema
from app.telegram.validators import normalize_telegram_channel_id


class ChannelCreate(BaseModel):
    telegram_channel_id: str = Field(min_length=1, max_length=64)
    title: str | None = Field(default=None, max_length=255)
    is_active: bool = True

    @field_validator("telegram_channel_id")
    @classmethod
    def validate_telegram_channel_id(cls, value: str) -> str:
        return normalize_telegram_channel_id(value)


class ChannelUpdate(BaseModel):
    telegram_channel_id: str | None = Field(default=None, min_length=1, max_length=64)
    title: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None

    @field_validator("telegram_channel_id")
    @classmethod
    def validate_telegram_channel_id(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return normalize_telegram_channel_id(value)


class ChannelRead(TimestampSchema):
    id: UUID
    telegram_channel_id: str
    title: str | None
    username: str | None
    bot_permission_status: BotPermissionStatus
    can_post_messages: bool
    can_edit_messages: bool
    can_delete_messages: bool
    permissions_checked_at: datetime | None
    permission_detail: str | None
    is_active: bool


class ChannelListResponse(PaginatedResponse):
    items: list[ChannelRead]
