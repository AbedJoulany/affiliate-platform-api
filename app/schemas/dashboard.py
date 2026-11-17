from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.core.enums import ProductStatus, QueueStatus


class ProductTotals(BaseModel):
    total: int
    by_status: dict[ProductStatus, int]


class QueueCounts(BaseModel):
    total: int
    by_status: dict[QueueStatus, int]


class ChannelCounts(BaseModel):
    total: int
    active: int
    inactive: int


class RecentActivity(BaseModel):
    resource_type: Literal["product", "queue"]
    resource_id: UUID
    title: str
    status: str
    occurred_at: datetime


class DashboardSystemStatus(BaseModel):
    status: Literal["operational"]
    database: Literal["up"]
    generated_at: datetime


class DashboardReporting(BaseModel):
    timezone: str
    day_start_utc: datetime
    day_end_utc: datetime
    generated_at: datetime


class PublishingProviderCounts(BaseModel):
    published: int
    failed: int


class PublishingByProvider(BaseModel):
    telegram: PublishingProviderCounts
    facebook: PublishingProviderCounts


class DashboardPublishing(BaseModel):
    published_today: int
    failed_today: int
    ambiguous_unresolved: int
    by_provider: PublishingByProvider


class DashboardAttentionItem(BaseModel):
    queue_id: UUID
    title: str
    provider: Literal["telegram", "facebook"]
    issue: Literal["failed", "ambiguous"]
    error_code: str | None
    message: str | None
    occurred_at: datetime


class TelegramDestinationReadiness(BaseModel):
    total: int
    active: int
    permission_granted: int


class FacebookDestinationReadiness(BaseModel):
    total: int
    active: int
    validated: int
    publishing_permission_verified: bool


class DashboardDestinationReadiness(BaseModel):
    telegram: TelegramDestinationReadiness
    facebook: FacebookDestinationReadiness


class DashboardAutomation(BaseModel):
    status: Literal["not_configured"]
    last_run_at: datetime | None


class DashboardResponse(BaseModel):
    products: ProductTotals
    queue: QueueCounts
    channels: ChannelCounts
    recent_activity: list[RecentActivity]
    system_status: DashboardSystemStatus
    reporting: DashboardReporting
    publishing: DashboardPublishing
    attention_items: list[DashboardAttentionItem]
    destination_readiness: DashboardDestinationReadiness
    automation: DashboardAutomation
