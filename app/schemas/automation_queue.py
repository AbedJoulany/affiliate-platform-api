from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.enums import AutomationProvider
from app.schemas.automation_policy import AutomationDestinationRead


class AutomationQueuePrepareRequest(BaseModel):
    expected_policy_revision: int = Field(ge=1)
    max_products: int = Field(default=2, ge=1, le=2)
    acknowledge_ai_cost: Literal[True]
    confirm_scheduled_publishing: Literal[True]
    idempotency_key: str = Field(min_length=8, max_length=128)

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, value: str) -> str:
        if not value.strip() or any(
            character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._:-"
            for character in value
        ):
            raise ValueError("idempotency_key contains unsupported characters")
        return value


AutomationQueueProductStatus = Literal[
    "scheduled",
    "skipped_ineligible",
    "skipped_duplicate",
    "skipped_no_available_slot",
    "failed_generation",
    "failed_validation",
    "failed_destination",
    "failed_queue",
    "skipped_after_global_failure",
]


class AutomationQueueProductResult(BaseModel):
    product_id: UUID
    selection_rank: int = Field(ge=1)
    recommendation_score: float | None = None
    status: AutomationQueueProductStatus
    queue_item_id: UUID | None = None
    scheduled_at: datetime | None = None
    warnings: list[str] = Field(default_factory=list)
    error_category: str | None = None


class AutomationQueuePrepareResponse(BaseModel):
    preview_only: Literal[False] = False
    execution_available: Literal[False] = False
    workspace_id: UUID
    policy_id: UUID
    policy_revision: int
    prepared_at: datetime
    scheduled_publishing_confirmed: Literal[True] = True
    provider: AutomationProvider
    destination: AutomationDestinationRead
    selected_count: int = Field(ge=0, le=2)
    generated_count: int = Field(ge=0, le=2)
    scheduled_count: int = Field(ge=0, le=2)
    skipped_count: int = Field(ge=0, le=2)
    failed_count: int = Field(ge=0, le=2)
    results: list[AutomationQueueProductResult]
    warnings: list[str] = Field(default_factory=list)
