from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from app.core.enums import QueueStatus
from app.schemas.common import PaginatedResponse, TimestampSchema


class QueueCreate(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    content: str = Field(min_length=1)
    status: QueueStatus = QueueStatus.DRAFT
    scheduled_at: datetime | None = None
    channel_id: UUID | None = None
    product_id: UUID | None = None
    image_url: HttpUrl | str | None = None
    button_text: str | None = Field(default=None, max_length=128)
    button_url: HttpUrl | str | None = None

    @model_validator(mode="after")
    def validate_scheduling(self) -> "QueueCreate":
        if self.status == QueueStatus.SCHEDULED and self.scheduled_at is None:
            raise ValueError("scheduled_at is required when status is scheduled")
        if self.status != QueueStatus.SCHEDULED:
            self.scheduled_at = None
        return self

    @model_validator(mode="after")
    def validate_button(self) -> "QueueCreate":
        if bool(self.button_text) != bool(self.button_url):
            raise ValueError("button_text and button_url must be provided together")
        return self


class QueueUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    content: str | None = Field(default=None, min_length=1)
    status: QueueStatus | None = None
    scheduled_at: datetime | None = None
    channel_id: UUID | None = None
    product_id: UUID | None = None
    image_url: HttpUrl | str | None = None
    button_text: str | None = Field(default=None, max_length=128)
    button_url: HttpUrl | str | None = None

    @model_validator(mode="after")
    def validate_scheduling(self) -> "QueueUpdate":
        if self.status == QueueStatus.SCHEDULED and self.scheduled_at is None:
            raise ValueError("scheduled_at is required when status is scheduled")
        return self

    @model_validator(mode="after")
    def validate_button(self) -> "QueueUpdate":
        if self.button_text is None and self.button_url is None:
            return self
        if bool(self.button_text) != bool(self.button_url):
            raise ValueError("button_text and button_url must be provided together")
        return self


class QueuePublishAttemptRead(BaseModel):
    """Attempt-scoped publish history row. ``status`` is not a QueueStatus value."""

    model_config = ConfigDict(from_attributes=True)

    attempt_number: int
    status: str
    provider: str
    occurred_at: datetime
    error_code: str | None = None
    error_message: str | None = None
    provider_chat_id: str | None = None
    provider_message_id: int | None = None


class QueuePublishAttemptListResponse(BaseModel):
    queue_id: UUID
    items: list[QueuePublishAttemptRead]
    total: int


class QueueRead(TimestampSchema):
    id: UUID
    title: str | None
    content: str
    status: QueueStatus
    scheduled_at: datetime | None
    published_at: datetime | None
    channel_id: UUID | None
    product_id: UUID | None
    image_url: str | None
    button_text: str | None
    button_url: str | None
    telegram_message_id: int | None
    # Additive attempt summary fields (None when not loaded, e.g. list responses).
    last_attempt: QueuePublishAttemptRead | None = None
    failure_reason: str | None = None
    retry_count: int = 0


class QueueListResponse(PaginatedResponse):
    items: list[QueueRead]


class PublishQueueResponse(BaseModel):
    queue_id: UUID
    telegram_message_id: int
    chat_id: str
    message_type: str
    published_at: datetime
