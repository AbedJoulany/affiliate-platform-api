from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.enums import AIProviderType


class AutomationContentPreviewRequest(BaseModel):
    expected_policy_revision: int = Field(ge=1)
    max_products: int = Field(default=2, ge=1, le=2)
    acknowledge_ai_cost: Literal[True]
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


AutomationContentStatus = Literal[
    "generated",
    "skipped_ineligible",
    "failed_not_found",
    "failed_validation",
    "failed_provider",
    "failed_timeout",
    "failed_configuration",
    "skipped_after_global_failure",
]


class AutomationContentProductResult(BaseModel):
    product_id: UUID
    selection_rank: int = Field(ge=1)
    recommendation_score: float | None = None
    status: AutomationContentStatus
    content: str | None = None
    affiliate_url: str | None = None
    requires_human_review: bool = False
    warnings: list[str] = Field(default_factory=list)
    error_category: str | None = None


class AutomationContentPreviewResponse(BaseModel):
    preview_only: Literal[True] = True
    execution_available: Literal[False] = False
    workspace_id: UUID
    policy_id: UUID
    policy_revision: int
    generated_at: datetime
    source: Literal["catalog"] = "catalog"
    requested_max_products: int = Field(ge=1, le=2)
    selected_count: int = Field(ge=0, le=2)
    generated_count: int = Field(ge=0, le=2)
    failed_count: int = Field(ge=0, le=2)
    provider: AIProviderType
    results: list[AutomationContentProductResult]
    warnings: list[str] = Field(default_factory=list)
