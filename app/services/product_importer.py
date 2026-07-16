from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.aliexpress.schemas import AliExpressProductData
from app.aliexpress.scoring import calculate_initial_product_score
from app.aliexpress.url_parser import AliExpressURLParser
from app.core.enums import ProductStatus
from app.models.product import Product
from app.repositories.product import ProductRepository


@dataclass
class ProductUpsertResult:
    product: Product
    imported: bool


class ProductImporter:
    """Shared upsert logic for AliExpress import and discovery persistence."""

    def __init__(
        self,
        session: AsyncSession,
        url_parser: AliExpressURLParser | None = None,
    ) -> None:
        self.session = session
        self.url_parser = url_parser or AliExpressURLParser()
        self.product_repo = ProductRepository(session)

    async def upsert_product(self, data: AliExpressProductData) -> ProductUpsertResult:
        canonical_url = self.url_parser.build_product_url(data.aliexpress_product_id)
        existing = await self._find_existing(data, canonical_url)

        if existing:
            product = await self._update_product(existing, data, canonical_url)
            return ProductUpsertResult(product=product, imported=False)

        product = await self._create_product(data, canonical_url)
        return ProductUpsertResult(product=product, imported=True)

    async def upsert_many(self, products: list[AliExpressProductData]) -> tuple[int, int]:
        imported = 0
        updated = 0
        for data in products:
            result = await self.upsert_product(data)
            if result.imported:
                imported += 1
            else:
                updated += 1
        return imported, updated

    async def _find_existing(
        self,
        data: AliExpressProductData,
        canonical_url: str,
    ) -> Product | None:
        existing = await self.product_repo.get_by_aliexpress_product_id(data.aliexpress_product_id)
        if existing:
            return existing

        existing = await self.product_repo.get_by_product_url(canonical_url)
        if existing:
            return existing

        if data.promotion_url:
            existing = await self.product_repo.get_by_affiliate_url(data.promotion_url)
            if existing:
                return existing
            existing = await self.product_repo.get_by_product_url(data.promotion_url)
            if existing:
                return existing

        return None

    async def _create_product(
        self,
        data: AliExpressProductData,
        canonical_url: str,
    ) -> Product:
        product = Product(
            aliexpress_product_id=data.aliexpress_product_id,
            title=data.title,
            description=data.description,
            price=data.price,
            original_price=data.original_price,
            discount=data.discount,
            rating=data.rating,
            sales=data.sales,
            reviews=data.reviews,
            image_url=data.image_url,
            gallery_images=data.images or None,
            product_url=canonical_url,
            affiliate_url=data.promotion_url,
            category=data.category,
            store_name=data.store_name,
            currency=data.currency,
            commission_rate=data.commission_rate,
            shipping_info=data.shipping_info,
            score=calculate_initial_product_score(
                rating=data.rating,
                sales=data.sales,
                discount=data.discount,
                reviews=data.reviews,
            ),
            status=ProductStatus.DRAFT,
            last_synced_at=data.last_synced_at,
        )
        return await self.product_repo.create(product)

    async def _update_product(
        self,
        product: Product,
        data: AliExpressProductData,
        canonical_url: str,
    ) -> Product:
        product.aliexpress_product_id = data.aliexpress_product_id
        product.title = data.title
        product.description = data.description
        product.price = data.price
        product.original_price = data.original_price
        product.discount = data.discount
        product.rating = data.rating
        product.sales = data.sales
        product.reviews = data.reviews
        product.image_url = data.image_url
        product.gallery_images = data.images or None
        product.product_url = canonical_url
        product.affiliate_url = data.promotion_url
        product.category = data.category
        product.store_name = data.store_name
        product.currency = data.currency
        product.commission_rate = data.commission_rate
        product.shipping_info = data.shipping_info
        product.score = calculate_initial_product_score(
            rating=data.rating,
            sales=data.sales,
            discount=data.discount,
            reviews=data.reviews,
        )
        product.last_synced_at = data.last_synced_at
        return await self.product_repo.update(product)
