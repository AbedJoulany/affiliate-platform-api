from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.aliexpress.schemas import AliExpressProductData
from app.models.product import Product
from app.services.product_importer import ProductImporter


@pytest.fixture
def importer(session: AsyncSession):
    return ProductImporter(session)


def _unique_product_id() -> str:
    return str(uuid4().int % 10**12).zfill(12)


def _sample_data(product_id: str | None = None) -> AliExpressProductData:
    product_id = product_id or _unique_product_id()
    return AliExpressProductData(
        aliexpress_product_id=product_id,
        title="Wireless Earbuds",
        image_url="https://example.com/main.jpg",
        images=["https://example.com/main.jpg", "https://example.com/alt.jpg"],
        price=Decimal("29.99"),
        original_price=Decimal("49.99"),
        discount=Decimal("40.00"),
        rating=Decimal("4.60"),
        sales=2500,
        reviews=120,
        product_url=f"https://www.aliexpress.com/item/{product_id}.html",
        promotion_url=f"https://s.click.aliexpress.com/e/_{product_id}",
        currency="USD",
        category="Electronics",
        store_name="Example Store",
        commission_rate=Decimal("7.00"),
        shipping_info={"ship_to_days": "7"},
    )


@pytest.mark.asyncio
async def test_importer_creates_new_product(importer: ProductImporter):
    data = _sample_data()
    result = await importer.upsert_product(data)

    assert result.imported is True
    assert result.product.aliexpress_product_id == data.aliexpress_product_id
    assert result.product.title == data.title
    assert result.product.affiliate_url == data.promotion_url
    assert result.product.gallery_images == data.images
    assert result.product.score > Decimal("0")


@pytest.mark.asyncio
async def test_importer_updates_existing_product_by_aliexpress_id(
    importer: ProductImporter,
    session: AsyncSession,
):
    product_id = _unique_product_id()
    existing = Product(
        aliexpress_product_id=product_id,
        title="Old Title",
        price=Decimal("10.00"),
        discount=Decimal("0.00"),
        rating=Decimal("1.00"),
        sales=1,
        reviews=0,
        image_url="https://example.com/old.jpg",
        product_url=f"https://www.aliexpress.com/item/{product_id}.html",
        score=Decimal("1.0000"),
    )
    session.add(existing)
    await session.flush()

    data = _sample_data(product_id)
    result = await importer.upsert_product(data)

    assert result.imported is False
    assert result.product.id == existing.id
    assert result.product.title == "Wireless Earbuds"
    assert result.product.sales == 2500


@pytest.mark.asyncio
async def test_importer_upsert_many_counts_created_and_updated(importer: ProductImporter):
    id_one = _unique_product_id()
    id_two = _unique_product_id()
    id_three = _unique_product_id()
    id_four = _unique_product_id()

    first = await importer.upsert_product(_sample_data(id_one))
    second = await importer.upsert_product(_sample_data(id_one))
    third = await importer.upsert_product(_sample_data(id_two))

    imported, updated = await importer.upsert_many(
        [_sample_data(id_three), _sample_data(id_three), _sample_data(id_four)]
    )

    assert first.imported is True
    assert second.imported is False
    assert third.imported is True
    assert imported == 2
    assert updated == 1
