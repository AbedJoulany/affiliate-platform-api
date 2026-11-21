from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.enums import (
    AIProviderType,
    AutomationExecutionState,
    AutomationFrequency,
    AutomationProvider,
    ContentLanguage,
    ContentLength,
    ContentType,
    ToneProfile,
)


class AutomationDestinationPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: AutomationProvider
    channel_id: UUID | None = None
    page_id: UUID | None = None

    @model_validator(mode="after")
    def validate_provider_destination(self) -> "AutomationDestinationPatch":
        if self.provider == AutomationProvider.TELEGRAM:
            if self.channel_id is None or self.page_id is not None:
                raise ValueError("Telegram destinations require channel_id only")
        elif self.page_id is None or self.channel_id is not None:
            raise ValueError("Facebook destinations require page_id only")
        return self


class AutomationDiscoveryPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keywords: str | None = Field(default=None, max_length=255)
    min_price: Decimal | None = Field(default=None, ge=0)
    max_price: Decimal | None = Field(default=None, ge=0)
    min_rating: Decimal | None = Field(default=None, ge=0, le=5)
    min_orders: int | None = Field(default=None, ge=0)
    min_discount: Decimal | None = Field(default=None, ge=0, le=100)
    min_commission: Decimal | None = Field(default=None, ge=0, le=100)
    max_commission: Decimal | None = Field(default=None, ge=0, le=100)
    products_per_run: int | None = Field(default=None, ge=1, le=50)

    @model_validator(mode="after")
    def validate_ranges(self) -> "AutomationDiscoveryPatch":
        if "products_per_run" in self.model_fields_set and self.products_per_run is None:
            raise ValueError("products_per_run cannot be null")
        if self.min_price is not None and self.max_price is not None:
            if self.min_price > self.max_price:
                raise ValueError("min_price must be less than or equal to max_price")
        if self.min_commission is not None and self.max_commission is not None:
            if self.min_commission > self.max_commission:
                raise ValueError(
                    "min_commission must be less than or equal to max_commission"
                )
        return self


class AutomationSchedulePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    frequency: AutomationFrequency | None = None
    preferred_time_local: str | None = Field(
        default=None,
        pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$",
    )
    posts_per_day: int | None = Field(default=None, ge=1, le=10)

    @model_validator(mode="after")
    def validate_non_nullable_fields(self) -> "AutomationSchedulePatch":
        for field in ("frequency", "preferred_time_local", "posts_per_day"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class AutomationContentPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ai_provider: AIProviderType | None = None
    language: ContentLanguage | None = None
    tone: ToneProfile | None = None
    content_type: ContentType | None = None
    length: ContentLength | None = None


class AutomationPolicyPatch(BaseModel):
    """Allow-listed partial policy update.

    ``expected_revision`` is optional only for the first write.  Existing rows
    require the current revision and reject stale updates with HTTP 409.
    """

    model_config = ConfigDict(extra="forbid")

    expected_revision: int | None = Field(default=None, ge=0)
    enabled: bool | None = None
    destination: AutomationDestinationPatch | None = None
    discovery: AutomationDiscoveryPatch | None = None
    schedule: AutomationSchedulePatch | None = None
    content: AutomationContentPatch | None = None

    @model_validator(mode="after")
    def validate_patch_sections(self) -> "AutomationPolicyPatch":
        if "enabled" in self.model_fields_set and self.enabled is None:
            raise ValueError("enabled cannot be null")
        for field in ("discovery", "schedule", "content"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class AutomationDestinationRead(BaseModel):
    provider: AutomationProvider
    channel_id: UUID | None = None
    page_id: UUID | None = None
    label: str | None = None
    active: bool | None = None
    ready: bool
    status: Literal[
        "ready",
        "missing",
        "inactive",
        "permission_missing",
        "not_validated",
        "unknown",
    ]


class AutomationDiscoveryRead(BaseModel):
    keywords: str | None
    min_price: Decimal | None
    max_price: Decimal | None
    min_rating: Decimal | None
    min_orders: int | None
    min_discount: Decimal | None
    min_commission: Decimal | None
    max_commission: Decimal | None
    products_per_run: int


class AutomationScheduleRead(BaseModel):
    frequency: AutomationFrequency
    preferred_time_local: str
    timezone: str
    posts_per_day: int


class AutomationContentRead(BaseModel):
    """Nullable fields are explicit workspace-setting inheritance overrides."""

    ai_provider: AIProviderType | None
    language: ContentLanguage | None
    tone: ToneProfile | None
    content_type: ContentType | None
    length: ContentLength | None


class AutomationPolicyRead(BaseModel):
    id: UUID | None
    workspace_id: UUID
    revision: int
    enabled: bool
    configuration_ready: bool
    execution_available: Literal[False]
    execution_state: AutomationExecutionState
    destination: AutomationDestinationRead | None
    discovery: AutomationDiscoveryRead
    schedule: AutomationScheduleRead
    content: AutomationContentRead
    warnings: list[str]
    created_at: datetime | None
    updated_at: datetime | None
