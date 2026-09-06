from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.aliexpress.response_parser import AliExpressPageMeta
from app.aliexpress.schemas import AliExpressProductData
from app.aliexpress.types import DiscoveryMode, ProductSortOption
from app.schemas.discovery import ProductDiscoveryQuery
from app.services.product_discovery import ProductDiscoveryService


def _product(
    product_id: str,
    *,
    rating: Decimal = Decimal("4.50"),
    sales: int = 100,
    discount: Decimal = Decimal("10.00"),
    price: Decimal = Decimal("19.99"),
    currency: str = "USD",
    platform: str | None = None,
    free_shipping: bool = False,
) -> AliExpressProductData:
    return AliExpressProductData(
        aliexpress_product_id=product_id,
        title=f"Product {product_id}",
        image_url="https://example.com/image.jpg",
        rating=rating,
        sales=sales,
        discount=discount,
        price=price,
        currency=currency,
        platform_product_type=platform,
        shipping_info={"free_shipping": True} if free_shipping else None,
    )


@pytest.fixture
def discovery_service():
    client = AsyncMock()
    return ProductDiscoveryService(client)


def test_dedupe_products(discovery_service):
    products = [
        _product("1"),
        _product("1"),
        _product("2"),
    ]
    result = discovery_service._dedupe_products(products)
    assert [item.aliexpress_product_id for item in result] == ["1", "2"]


def test_apply_filters(discovery_service):
    products = [
        _product(
            "1", rating=Decimal("4.80"), sales=500, discount=Decimal("30"), price=Decimal("10")
        ),
        _product("2", rating=Decimal("3.00"), sales=50, discount=Decimal("5"), price=Decimal("50")),
    ]
    query = ProductDiscoveryQuery(
        min_rating=Decimal("4.00"),
        min_orders=100,
        min_discount=Decimal("20"),
        max_price=Decimal("20"),
    )

    filtered = discovery_service._apply_filters(products, query)
    assert [item.aliexpress_product_id for item in filtered] == ["1"]


def test_apply_sort_orders_desc(discovery_service):
    products = [_product("1", sales=10), _product("2", sales=1000)]
    sorted_products = discovery_service._apply_sort(products, ProductSortOption.ORDERS_DESC)
    assert [item.aliexpress_product_id for item in sorted_products] == ["2", "1"]


@pytest.mark.asyncio
async def test_discover_hot_delegates_to_client(discovery_service):
    discovery_service.client.get_hot_products = AsyncMock(
        return_value=(
            [_product("99")],
            AliExpressPageMeta(1, 1, 1, 1, True),
        )
    )

    query = ProductDiscoveryQuery(mode=DiscoveryMode.HOT, page=1, page_size=10)
    result = await discovery_service.discover_hot(query)

    discovery_service.client.get_hot_products.assert_awaited_once()
    assert result.response.items[0].aliexpress_product_id == "99"
    assert result.response.mode is DiscoveryMode.HOT
