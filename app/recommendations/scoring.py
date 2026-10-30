"""Explainable recommendation scoring for persisted catalog products."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

SCORE_WEIGHTS: dict[str, Decimal] = {
    "rating": Decimal("0.30"),
    "orders": Decimal("0.20"),
    "discount": Decimal("0.15"),
    "price": Decimal("0.10"),
    "commission": Decimal("0.25"),
}
ZERO = Decimal("0")
ONE = Decimal("1")
HUNDRED = Decimal("100")
SCORE_QUANTUM = Decimal("0.0001")


@dataclass(frozen=True)
class ScoreFactor:
    key: str
    raw_value: Decimal | int | None
    normalized_value: Decimal
    weight: Decimal
    contribution: Decimal
    missing: bool


@dataclass(frozen=True)
class RecommendationScore:
    total: Decimal
    factors: tuple[ScoreFactor, ...]


def _decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _clamp(value: Decimal, minimum: Decimal = ZERO, maximum: Decimal = ONE) -> Decimal:
    return max(minimum, min(value, maximum))


def _factor(
    key: str,
    raw_value: Decimal | int | None,
    normalized_value: Decimal,
) -> ScoreFactor:
    weight = SCORE_WEIGHTS[key]
    return ScoreFactor(
        key=key,
        raw_value=raw_value,
        normalized_value=normalized_value.quantize(SCORE_QUANTUM, rounding=ROUND_HALF_UP),
        weight=weight,
        contribution=(normalized_value * weight * HUNDRED).quantize(
            SCORE_QUANTUM,
            rounding=ROUND_HALF_UP,
        ),
        missing=raw_value is None,
    )


def calculate_recommendation_score(
    product: Any,
    *,
    max_sales: int,
    min_price: Decimal,
    max_price: Decimal,
) -> RecommendationScore:
    """Calculate a candidate-set-relative, deterministic recommendation score.

    Price intentionally rewards lower prices within the already-filtered set.
    Orders use a logarithmic scale so very large sales counts do not dominate.
    """

    rating = _decimal(getattr(product, "rating", None))
    sales = getattr(product, "sales", None)
    discount = _decimal(getattr(product, "discount", None))
    price = _decimal(getattr(product, "price", None))
    commission = _decimal(getattr(product, "commission_rate", None))

    rating_score = ZERO if rating is None else _clamp(rating / Decimal("5"))

    if sales is None or max_sales <= 0:
        orders_score = ZERO
    else:
        import math

        orders_score = _clamp(
            Decimal(str(math.log1p(max(0, int(sales))) / math.log1p(max_sales)))
        )

    discount_score = ZERO if discount is None else _clamp(discount / HUNDRED)

    if price is None or max_price == min_price:
        price_score = ONE if price is not None else ZERO
    else:
        price_score = _clamp((max_price - price) / (max_price - min_price))

    commission_score = ZERO if commission is None else _clamp(commission / HUNDRED)

    factors = (
        _factor("rating", rating, rating_score),
        _factor("orders", sales, orders_score),
        _factor("discount", discount, discount_score),
        _factor("price", price, price_score),
        _factor("commission", commission, commission_score),
    )
    total = sum((factor.contribution for factor in factors), ZERO).quantize(
        SCORE_QUANTUM,
        rounding=ROUND_HALF_UP,
    )
    return RecommendationScore(total=total, factors=factors)
