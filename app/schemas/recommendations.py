from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.schemas.product import ProductRead


class RecommendationQuery(BaseModel):
    keywords: str | None = Field(default=None, max_length=255)
    min_price: Decimal | None = Field(default=None, ge=0)
    max_price: Decimal | None = Field(default=None, ge=0)
    min_rating: Decimal | None = Field(default=None, ge=0, le=5)
    min_orders: int | None = Field(default=None, ge=0)
    min_discount: Decimal | None = Field(default=None, ge=0, le=100)
    min_commission: Decimal | None = Field(default=None, ge=0)
    max_commission: Decimal | None = Field(default=None, ge=0)
    top_n: int = Field(default=10, ge=1, le=50)

    @model_validator(mode="after")
    def validate_ranges(self) -> "RecommendationQuery":
        if self.min_price is not None and self.max_price is not None:
            if self.min_price > self.max_price:
                raise ValueError("min_price must be less than or equal to max_price")
        if self.min_commission is not None and self.max_commission is not None:
            if self.min_commission > self.max_commission:
                raise ValueError("min_commission must be less than or equal to max_commission")
        return self


class RecommendationScoreFactor(BaseModel):
    key: str
    raw_value: Decimal | int | None
    normalized_value: Decimal
    weight: Decimal
    contribution: Decimal
    missing: bool


class RecommendationScoreBreakdown(BaseModel):
    total: Decimal
    factors: list[RecommendationScoreFactor]


class RecommendationItem(BaseModel):
    rank: int
    product: ProductRead
    recommendation_score: Decimal
    score_breakdown: RecommendationScoreBreakdown
    lacks_affiliate_url: bool


class RecommendationResponse(BaseModel):
    items: list[RecommendationItem]
    total_candidates: int
    returned: int
    top_n: int
