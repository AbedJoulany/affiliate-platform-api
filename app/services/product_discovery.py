from dataclasses import dataclass
from decimal import Decimal

from app.aliexpress.client import AliExpressAffiliateClient
from app.aliexpress.response_parser import AliExpressPageMeta
from app.aliexpress.schemas import AliExpressProductData
from app.aliexpress.scoring import calculate_initial_product_score
from app.aliexpress.types import (
    AliExpressAPISort,
    AliExpressPromoSort,
    DiscoveryMode,
    PlatformProductType,
    ProductSortOption,
)
from app.schemas.discovery import (
    DiscoveredProductRead,
    ProductDiscoveryQuery,
    ProductDiscoveryResponse,
    ProductSearchQuery,
)
from app.services.product_importer import ProductImporter


@dataclass
class DiscoveryResult:
    response: ProductDiscoveryResponse
    products: list[AliExpressProductData]


class ProductDiscoveryService:
    def __init__(
        self,
        client: AliExpressAffiliateClient,
        importer: ProductImporter | None = None,
    ) -> None:
        self.client = client
        self.importer = importer

    async def discover(self, query: ProductDiscoveryQuery) -> DiscoveryResult:
        products, meta = await self._fetch_by_mode(query)
        # ADD THIS TEMP LOG TO DEBUG:
        print("🔥 RAW FROM API:", len(products))
        print("🔥 SAMPLE:", products[:1])
        products = self._dedupe_products(products)
        #products = self._apply_filters(products, query)
        #products = self._apply_sort(products, query.sort)

        persisted_count = 0
        if query.persist and self.importer and products:
            imported, updated = await self.importer.upsert_many(products)
            persisted_count = imported + updated

        items = [self._to_discovered_read(item) for item in products]
        response = ProductDiscoveryResponse(
            items=items,
            total=meta.total_count,
            skip=(query.page - 1) * query.page_size,
            limit=query.page_size,
            page=meta.current_page,
            total_pages=meta.total_pages,
            mode=query.mode,
            sort=query.sort,
            persisted_count=persisted_count,
        )
        return DiscoveryResult(response=response, products=products)

    async def search(self, query: ProductSearchQuery) -> DiscoveryResult:
        discovery_query = ProductDiscoveryQuery(
            mode=DiscoveryMode.KEYWORD,
            sort=query.sort,
            page=query.page,
            page_size=query.page_size,
            persist=query.persist,
            keywords=query.q,
            category_id=query.category_id,
            min_rating=query.min_rating,
            min_orders=query.min_orders,
            min_price=query.min_price,
            max_price=query.max_price,
            min_discount=query.min_discount,
            shipping_country=query.shipping_country,
            currency=query.currency,
            choice_only=query.choice_only,
            free_shipping=query.free_shipping,
        )
        return await self.discover(discovery_query)

    async def discover_hot(self, query: ProductDiscoveryQuery) -> DiscoveryResult:
        query.mode = DiscoveryMode.HOT
        return await self.discover(query)

    async def discover_deals(self, query: ProductDiscoveryQuery) -> DiscoveryResult:
        query.mode = DiscoveryMode.DEALS
        return await self.discover(query)

    async def discover_trending(self, query: ProductDiscoveryQuery) -> DiscoveryResult:
        query.mode = DiscoveryMode.TRENDING
        return await self.discover(query)

    async def discover_by_category(
        self,
        category_id: str,
        query: ProductDiscoveryQuery,
    ) -> DiscoveryResult:
        query.mode = DiscoveryMode.CATEGORY
        query.category_id = category_id
        return await self.discover(query)

    async def _fetch_by_mode(
        self,
        query: ProductDiscoveryQuery,
    ) -> tuple[list[AliExpressProductData], AliExpressPageMeta]:
        api_sort = self._map_api_sort(query.sort)
        ship_to_country = query.shipping_country
        min_sale_price = self._price_to_cents(query.min_price)
        max_sale_price = self._price_to_cents(query.max_price)

        if query.mode is DiscoveryMode.HOT:
            return await self.client.get_hot_products(
                page_no=query.page,
                page_size=query.page_size,
                category_ids=query.category_id,
                keywords=query.keywords,
                sort=api_sort or AliExpressAPISort.LAST_VOLUME_DESC,
                ship_to_country=ship_to_country,
            )

        if query.mode is DiscoveryMode.TRENDING:
            return await self.client.get_trending_products(
                page_no=query.page,
                page_size=query.page_size,
                keywords=query.keywords,
                ship_to_country=ship_to_country,
            )

        if query.mode in (DiscoveryMode.DEALS, DiscoveryMode.BIG_DISCOUNT, DiscoveryMode.COMMISSION):
            promo_sort = self._map_promo_sort(query.sort, query.mode)
            return await self.client.get_featured_promo_products(
                page_no=query.page,
                page_size=query.page_size,
                category_id=query.category_id,
                promotion_name=query.promotion_name,
                sort=promo_sort,
                country=ship_to_country,
            )

        platform_type = PlatformProductType.PLAZA if query.choice_only else None
        if query.mode is DiscoveryMode.CHOICE:
            platform_type = PlatformProductType.PLAZA

        return await self.client.query_products(
            page_no=query.page,
            page_size=query.page_size,
            category_ids=query.category_id,
            keywords=query.keywords,
            min_sale_price=min_sale_price,
            max_sale_price=max_sale_price,
            sort=api_sort,
            platform_product_type=platform_type,
            ship_to_country=ship_to_country,
        )

    def _dedupe_products(self, products: list[AliExpressProductData]) -> list[AliExpressProductData]:
        seen: set[str] = set()
        unique: list[AliExpressProductData] = []
        for product in products:
            if product.aliexpress_product_id in seen:
                continue
            seen.add(product.aliexpress_product_id)
            unique.append(product)
        return unique

    def _apply_filters(
        self,
        products: list[AliExpressProductData],
        query: ProductDiscoveryQuery | ProductSearchQuery,
    ) -> list[AliExpressProductData]:
        filtered: list[AliExpressProductData] = []
        for product in products:
            if query.min_rating is not None and product.rating < query.min_rating:
                continue
            if query.min_orders is not None and product.sales < query.min_orders:
                continue
            if query.min_price is not None and product.price < query.min_price:
                continue
            if query.max_price is not None and product.price > query.max_price:
                continue
            if query.min_discount is not None and product.discount < query.min_discount:
                continue
            filtered.append(product)
        return filtered

    def _apply_sort(
        self,
        products: list[AliExpressProductData],
        sort: ProductSortOption,
    ) -> list[AliExpressProductData]:
        key_map = {
            ProductSortOption.ORDERS_DESC: lambda item: item.sales,
            ProductSortOption.RATING_DESC: lambda item: item.rating,
            ProductSortOption.DISCOUNT_DESC: lambda item: item.discount,
            ProductSortOption.PRICE_ASC: lambda item: item.price,
            ProductSortOption.PRICE_DESC: lambda item: item.price,
            ProductSortOption.COMMISSION_DESC: lambda item: item.commission_rate or Decimal("0"),
            ProductSortOption.NEWEST: lambda item: item.last_synced_at,
        }
        reverse = sort != ProductSortOption.PRICE_ASC
        return sorted(products, key=key_map[sort], reverse=reverse)

    def _map_api_sort(self, sort: ProductSortOption) -> AliExpressAPISort | None:
        mapping = {
            ProductSortOption.ORDERS_DESC: AliExpressAPISort.LAST_VOLUME_DESC,
            ProductSortOption.PRICE_ASC: AliExpressAPISort.SALE_PRICE_ASC,
            ProductSortOption.PRICE_DESC: AliExpressAPISort.SALE_PRICE_DESC,
        }
        return mapping.get(sort)

    def _map_promo_sort(
        self,
        sort: ProductSortOption,
        mode: DiscoveryMode,
    ) -> AliExpressPromoSort:
        if mode is DiscoveryMode.COMMISSION:
            return AliExpressPromoSort.COMMISSION_DESC
        if mode is DiscoveryMode.BIG_DISCOUNT:
            return AliExpressPromoSort.DISCOUNT_DESC

        mapping = {
            ProductSortOption.ORDERS_DESC: AliExpressPromoSort.VOLUME_DESC,
            ProductSortOption.RATING_DESC: AliExpressPromoSort.RATING_DESC,
            ProductSortOption.DISCOUNT_DESC: AliExpressPromoSort.DISCOUNT_DESC,
            ProductSortOption.PRICE_ASC: AliExpressPromoSort.PRICE_ASC,
            ProductSortOption.PRICE_DESC: AliExpressPromoSort.PRICE_DESC,
            ProductSortOption.COMMISSION_DESC: AliExpressPromoSort.COMMISSION_DESC,
        }
        return mapping.get(sort, AliExpressPromoSort.DISCOUNT_DESC)

    def _price_to_cents(self, value: Decimal | None) -> str | None:
        if value is None:
            return None
        return str(int(value * 100))

    def _to_discovered_read(self, product: AliExpressProductData) -> DiscoveredProductRead:
        return DiscoveredProductRead(
            aliexpress_product_id=product.aliexpress_product_id,
            title=product.title,
            description=product.description,
            price=product.price,
            original_price=product.original_price,
            discount=product.discount,
            rating=product.rating,
            sales=product.sales,
            reviews=product.reviews,
            image_url=product.image_url,
            gallery_images=product.images,
            product_url=product.product_url,
            affiliate_url=product.promotion_url,
            category=product.category,
            store_name=product.store_name,
            currency=product.currency,
            commission_rate=product.commission_rate,
            shipping_info=product.shipping_info,
            score=calculate_initial_product_score(
                rating=product.rating,
                sales=product.sales,
                discount=product.discount,
                reviews=product.reviews,
            ),
        )
