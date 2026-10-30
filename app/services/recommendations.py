from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.recommendations.scoring import RecommendationScore, calculate_recommendation_score
from app.schemas.recommendations import (
    RecommendationItem,
    RecommendationQuery,
    RecommendationResponse,
    RecommendationScoreBreakdown,
    RecommendationScoreFactor,
)

TOKEN_PATTERN = re.compile(r"\S+", re.UNICODE)


@dataclass(frozen=True)
class _RankedProduct:
    product: Product
    score: RecommendationScore


class RecommendationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def recommend(self, query: RecommendationQuery) -> RecommendationResponse:
        products = await self._load_candidates(query)
        products = [
            product for product in products if self._matches_keywords(product, query.keywords)
        ]

        if not products:
            return RecommendationResponse(
                items=[],
                total_candidates=0,
                returned=0,
                top_n=query.top_n,
            )

        prices = [product.price for product in products]
        min_price = min(prices)
        max_price = max(prices)
        max_sales = max(max(0, product.sales) for product in products)

        ranked = [
            _RankedProduct(
                product=product,
                score=calculate_recommendation_score(
                    product,
                    max_sales=max_sales,
                    min_price=min_price,
                    max_price=max_price,
                ),
            )
            for product in products
        ]
        ranked.sort(key=self._ranking_key)
        selected = ranked[: query.top_n]

        return RecommendationResponse(
            items=[self._to_item(index, item) for index, item in enumerate(selected, start=1)],
            total_candidates=len(ranked),
            returned=len(selected),
            top_n=query.top_n,
        )

    async def _load_candidates(self, query: RecommendationQuery) -> list[Product]:
        statement = select(Product)
        if query.min_price is not None:
            statement = statement.where(Product.price >= query.min_price)
        if query.max_price is not None:
            statement = statement.where(Product.price <= query.max_price)
        if query.min_rating is not None:
            statement = statement.where(Product.rating >= query.min_rating)
        if query.min_orders is not None:
            statement = statement.where(Product.sales >= query.min_orders)
        if query.min_discount is not None:
            statement = statement.where(Product.discount >= query.min_discount)
        if query.min_commission is not None:
            statement = statement.where(Product.commission_rate >= query.min_commission)
        if query.max_commission is not None:
            statement = statement.where(Product.commission_rate <= query.max_commission)

        statement = statement.order_by(Product.aliexpress_product_id.asc(), Product.id.asc())
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    def _matches_keywords(self, product: Product, keywords: str | None) -> bool:
        tokens = [token.casefold() for token in TOKEN_PATTERN.findall(keywords or "")]
        if not tokens:
            return True
        searchable = " ".join(
            value or ""
            for value in (product.title, product.description, product.category, product.store_name)
        ).casefold()
        return all(token in searchable for token in tokens)

    def _ranking_key(self, item: _RankedProduct) -> tuple:
        product = item.product
        commission = (
            product.commission_rate
            if product.commission_rate is not None
            else Decimal("-1")
        )
        return (
            -item.score.total,
            -product.rating,
            -product.sales,
            -commission,
            product.price,
            product.aliexpress_product_id or "",
            str(product.id),
        )

    def _to_item(self, rank: int, item: _RankedProduct) -> RecommendationItem:
        affiliate_url = item.product.affiliate_url
        return RecommendationItem(
            rank=rank,
            product=item.product,
            recommendation_score=item.score.total,
            score_breakdown=RecommendationScoreBreakdown(
                total=item.score.total,
                factors=[
                    RecommendationScoreFactor.model_validate(factor.__dict__)
                    for factor in item.score.factors
                ],
            ),
            lacks_affiliate_url=not self._has_valid_affiliate_url(affiliate_url),
        )

    @staticmethod
    def _has_valid_affiliate_url(value: str | None) -> bool:
        if not value or not value.strip():
            return False
        parsed = urlparse(value.strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
