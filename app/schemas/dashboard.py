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


class DashboardResponse(BaseModel):
    products: ProductTotals
    queue: QueueCounts
    channels: ChannelCounts
    recent_activity: list[RecentActivity]
    system_status: DashboardSystemStatus
