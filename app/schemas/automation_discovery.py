from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AutomationDiscoverySelectedProduct(BaseModel):
    product_id: UUID
    rank: int = Field(ge=1)
    recommendation_score: Decimal
    affiliate_url_present: Literal[True] = True


class AutomationDiscoveryExcludedCounts(BaseModel):
    """Counts among the bounded, inspected catalog slice only."""

    model_config = ConfigDict(extra="forbid")

    missing_affiliate_url: int = Field(default=0, ge=0)
    queued_or_scheduled: int = Field(default=0, ge=0)
    recently_published: int = Field(default=0, ge=0)
    unresolved_ambiguous: int = Field(default=0, ge=0)
    keyword_mismatch: int = Field(default=0, ge=0)


class AutomationDiscoveryPreviewResponse(BaseModel):
    preview_only: Literal[True] = True
    execution_available: Literal[False] = False
    workspace_id: UUID
    policy_id: UUID
    policy_revision: int
    policy_enabled: bool
    configuration_ready: bool
    selection_timestamp: datetime
    source: Literal["catalog"] = "catalog"
    candidate_cap: int = Field(default=1000, gt=0)
    truncated: bool
    ranking_scope: Literal["inspected_candidates_only"] = "inspected_candidates_only"
    candidates_inspected: int = Field(ge=0)
    eligible_count: int = Field(ge=0)
    selected_count: int = Field(ge=0)
    selected_products: list[AutomationDiscoverySelectedProduct]
    excluded_counts: AutomationDiscoveryExcludedCounts
    warnings: list[str]
