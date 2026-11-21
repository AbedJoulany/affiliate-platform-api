from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProductStatus
from app.models.aliexpress_category import AliExpressCategory
from app.models.product import Product
from app.repositories.base import BaseRepository


class ProductRepository(BaseRepository[Product]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Product)

    def _build_filters(
        self,
        *,
        title: str | None = None,
        status: ProductStatus | None = None,
    ) -> list:
        filters = []
        if title:
            filters.append(Product.title.ilike(f"%{title}%"))
        if status is not None:
            filters.append(Product.status == status)
        return filters

    async def search(
        self,
        *,
        title: str | None = None,
        status: ProductStatus | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Product], int]:
        filters = self._build_filters(title=title, status=status)

        count_query = select(func.count()).select_from(Product)
        if filters:
            count_query = count_query.where(*filters)
        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()

        items_query = select(Product)
        if filters:
            items_query = items_query.where(*filters)
        items_query = items_query.order_by(Product.created_at.desc()).offset(skip).limit(limit)

        result = await self.session.execute(items_query)
        return list(result.scalars().all()), total

    async def get_by_product_url(self, product_url: str) -> Product | None:
        result = await self.session.execute(
            select(Product).where(Product.product_url == product_url)
        )
        return result.scalar_one_or_none()

    async def get_by_affiliate_url(self, affiliate_url: str) -> Product | None:
        result = await self.session.execute(
            select(Product).where(Product.affiliate_url == affiliate_url)
        )
        return result.scalar_one_or_none()

    async def get_by_aliexpress_product_id(self, aliexpress_product_id: str) -> Product | None:
        result = await self.session.execute(
            select(Product).where(Product.aliexpress_product_id == aliexpress_product_id)
        )
        return result.scalar_one_or_none()

    async def list_active_recommendation_candidates(
        self,
        *,
        min_price: Decimal | None = None,
        max_price: Decimal | None = None,
        min_rating: Decimal | None = None,
        min_orders: int | None = None,
        min_discount: Decimal | None = None,
        min_commission: Decimal | None = None,
        max_commission: Decimal | None = None,
        keyword_tokens: tuple[str, ...] = (),
        limit: int = 1001,
    ) -> list[Product]:
        """Return a deterministically bounded active catalog slice.

        Numeric recommendation filters and an optional database keyword
        prefilter are applied before the limit. Exact keyword matching and
        score normalization remain in RecommendationService.
        """
        filters = [Product.status == ProductStatus.ACTIVE]
        if min_price is not None:
            filters.append(Product.price >= min_price)
        if max_price is not None:
            filters.append(Product.price <= max_price)
        if min_rating is not None:
            filters.append(Product.rating >= min_rating)
        if min_orders is not None:
            filters.append(Product.sales >= min_orders)
        if min_discount is not None:
            filters.append(Product.discount >= min_discount)
        if min_commission is not None:
            filters.append(Product.commission_rate >= min_commission)
        if max_commission is not None:
            filters.append(Product.commission_rate <= max_commission)
        if keyword_tokens:
            searchable_fields = (
                Product.title,
                Product.description,
                Product.category,
                Product.store_name,
            )
            for token in keyword_tokens:
                escaped_token = (
                    token.replace("\\", "\\\\")
                    .replace("%", "\\%")
                    .replace("_", "\\_")
                )
                filters.append(
                    or_(
                        *(
                            field.ilike(
                                f"%{escaped_token}%",
                                escape="\\",
                            )
                            for field in searchable_fields
                        )
                    )
                )

        statement = (
            select(Product)
            .where(*filters)
            .order_by(
                Product.aliexpress_product_id.asc().nulls_last(),
                Product.id.asc(),
            )
            .limit(limit)
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())


class AliExpressCategoryRepository(BaseRepository[AliExpressCategory]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AliExpressCategory)

    async def list_all(self) -> list[AliExpressCategory]:
        result = await self.session.execute(
            select(AliExpressCategory).order_by(
                AliExpressCategory.parent_category_id,
                AliExpressCategory.category_name,
            )
        )
        return list(result.scalars().all())

    async def replace_all(self, categories: list[AliExpressCategory]) -> int:
        await self.session.execute(delete(AliExpressCategory))
        synced_at = datetime.now(UTC)
        for category in categories:
            category.synced_at = synced_at
            self.session.add(category)
        await self.session.flush()
        return len(categories)
