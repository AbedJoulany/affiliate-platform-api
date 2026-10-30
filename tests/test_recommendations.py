from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.recommendations.scoring import calculate_recommendation_score
from app.schemas.recommendations import RecommendationQuery
from app.services.recommendations import RecommendationService


def _product(**overrides):
    values = {
        "rating": Decimal("4.00"),
        "sales": 100,
        "discount": Decimal("20.00"),
        "price": Decimal("20.00"),
        "commission_rate": Decimal("5.00"),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_recommendation_score_uses_weights_and_exposes_factors():
    result = calculate_recommendation_score(
        _product(
            rating=Decimal("5"),
            sales=1000,
            discount=Decimal("100"),
            price=Decimal("10"),
            commission_rate=Decimal("100"),
        ),
        max_sales=1000,
        min_price=Decimal("10"),
        max_price=Decimal("20"),
    )

    assert result.total == Decimal("100.0000")
    assert [factor.key for factor in result.factors] == [
        "rating",
        "orders",
        "discount",
        "price",
        "commission",
    ]
    assert all(factor.contribution >= 0 for factor in result.factors)


def test_lower_price_scores_higher_and_equal_prices_are_neutral():
    cheaper = calculate_recommendation_score(
        _product(price=Decimal("10")),
        max_sales=100,
        min_price=Decimal("10"),
        max_price=Decimal("20"),
    )
    expensive = calculate_recommendation_score(
        _product(price=Decimal("20")),
        max_sales=100,
        min_price=Decimal("10"),
        max_price=Decimal("20"),
    )
    equal = calculate_recommendation_score(
        _product(price=Decimal("10")),
        max_sales=100,
        min_price=Decimal("10"),
        max_price=Decimal("10"),
    )

    assert cheaper.total > expensive.total
    assert equal.factors[3].normalized_value == Decimal("1.0000")


def test_missing_commission_is_reported_and_scores_zero():
    result = calculate_recommendation_score(
        _product(commission_rate=None),
        max_sales=100,
        min_price=Decimal("10"),
        max_price=Decimal("20"),
    )

    commission = result.factors[-1]
    assert commission.missing is True
    assert commission.normalized_value == Decimal("0.0000")
    assert commission.contribution == Decimal("0.0000")


def test_affiliate_url_warning_rejects_blank_or_non_http_values():
    service = RecommendationService.__new__(RecommendationService)

    assert service._has_valid_affiliate_url("https://example.com/affiliate") is True
    assert service._has_valid_affiliate_url(" ") is False
    assert service._has_valid_affiliate_url("not-a-url") is False


def test_query_validates_inclusive_range_order():
    assert RecommendationQuery(min_price=10, max_price=10).min_price == Decimal("10")
    with pytest.raises(ValueError):
        RecommendationQuery(min_commission=9, max_commission=8)


def test_keyword_matching_requires_all_tokens():
    service = RecommendationService.__new__(RecommendationService)
    product = SimpleNamespace(
        title="Wireless Earbuds",
        description="Noise cancelling audio",
        category="Electronics",
        store_name="Audio Store",
    )

    assert service._matches_keywords(product, "wireless AUDIO") is True
    assert service._matches_keywords(product, "wireless camera") is False


def _catalog_product(**overrides) -> Product:
    values = {
        "aliexpress_product_id": str(uuid4().int % 10**12).zfill(12),
        "title": "Wireless Earbuds",
        "description": "Noise cancelling audio",
        "price": Decimal("20.00"),
        "discount": Decimal("20.00"),
        "rating": Decimal("4.00"),
        "sales": 100,
        "reviews": 10,
        "image_url": "https://example.com/image.jpg",
        "product_url": "https://www.aliexpress.com/item/example.html",
        "affiliate_url": "https://s.click.aliexpress.com/e/example",
        "commission_rate": Decimal("5.00"),
    }
    values.update(overrides)
    return Product(**values)


@pytest.mark.asyncio
async def test_service_applies_commission_filters_and_top_n(session: AsyncSession):
    session.add_all(
        [
            _catalog_product(price=Decimal("10"), commission_rate=Decimal("8")),
            _catalog_product(price=Decimal("20"), commission_rate=Decimal("3")),
            _catalog_product(price=Decimal("30"), commission_rate=None),
        ]
    )
    await session.flush()

    response = await RecommendationService(session).recommend(
        RecommendationQuery(
            keywords="wireless audio",
            min_commission=Decimal("5"),
            max_price=Decimal("20"),
            top_n=1,
        )
    )

    assert response.total_candidates == 1
    assert response.returned == 1
    assert response.items[0].rank == 1
    assert response.items[0].product.commission_rate == Decimal("8")
    assert response.items[0].lacks_affiliate_url is False


@pytest.mark.asyncio
async def test_service_returns_empty_response_when_no_products_match(session: AsyncSession):
    session.add(_catalog_product(title="Kitchen Lamp", commission_rate=Decimal("2")))
    await session.flush()

    response = await RecommendationService(session).recommend(
        RecommendationQuery(keywords="camera", min_commission=Decimal("10"))
    )

    assert response.items == []
    assert response.total_candidates == 0
    assert response.returned == 0


@pytest.mark.asyncio
async def test_recommendation_endpoint_requires_authentication(client):
    response = await client.get("/api/v1/products/recommendations")

    assert response.status_code == 401
