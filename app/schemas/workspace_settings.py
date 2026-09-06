from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import (
    AIProviderType,
    ContentLanguage,
    ContentLength,
    ContentType,
    ToneProfile,
)

_TZ_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789/_-+")


class WorkspaceDiscoveryMode(StrEnum):
    GENERAL = "general"
    HOT = "hot"
    DEALS = "deals"
    TRENDING = "trending"
    CATEGORY = "category"


class ProviderConnectionStatus(BaseModel):
    """Booleans derived from whether env vars are set — never the values."""

    aliexpress: bool
    telegram_bot: bool
    openai: bool
    gemini: bool
    image_search: bool


class WorkspaceSettingsPatch(BaseModel):
    """Allow-list of editable workspace settings. Unknown keys → 422."""

    model_config = ConfigDict(extra="forbid")

    timezone: str | None = Field(default=None, min_length=1, max_length=64)
    ui_language: Literal["ar", "en"] | None = None
    aliexpress_target_currency: str | None = Field(default=None, min_length=3, max_length=3)
    aliexpress_ship_to_country: str | None = Field(default=None, min_length=2, max_length=2)
    aliexpress_target_language: str | None = Field(default=None, min_length=2, max_length=8)
    default_ai_provider: AIProviderType | None = None
    default_content_type: ContentType | None = None
    default_tone: ToneProfile | None = None
    default_content_language: ContentLanguage | None = None
    default_content_length: ContentLength | None = None
    discovery_default_mode: WorkspaceDiscoveryMode | None = None
    discovery_page_size: int | None = Field(default=None, ge=1, le=50)
    default_telegram_channel_id: UUID | None = None

    @field_validator("timezone")
    @classmethod
    def timezone_looks_like_iana(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value != "UTC" and (
            "/" not in value or any(char not in _TZ_CHARS for char in value)
        ):
            raise ValueError("Invalid timezone")
        return value

    @field_validator("aliexpress_target_currency")
    @classmethod
    def currency_upper(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value.isalpha():
            raise ValueError("Currency must be a 3-letter ISO code")
        return value.upper()

    @field_validator("aliexpress_ship_to_country")
    @classmethod
    def country_upper(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value.isalpha():
            raise ValueError("Country must be a 2-letter ISO code")
        return value.upper()

    @field_validator("aliexpress_target_language")
    @classmethod
    def language_upper(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value.isalpha():
            raise ValueError("Language must be an alphabetic code")
        return value.upper()


class WorkspaceSettingsRead(BaseModel):
    workspace_id: UUID
    can_edit: bool
    timezone: str
    ui_language: Literal["ar", "en"]
    aliexpress_target_currency: str
    aliexpress_ship_to_country: str
    aliexpress_target_language: str
    default_ai_provider: AIProviderType
    default_content_type: ContentType
    default_tone: ToneProfile
    default_content_language: ContentLanguage
    default_content_length: ContentLength
    discovery_default_mode: WorkspaceDiscoveryMode
    discovery_page_size: int
    default_telegram_channel_id: UUID | None
    connections: ProviderConnectionStatus
    created_at: datetime | None = None
    updated_at: datetime | None = None
