from datetime import UTC, datetime

from sqlalchemy import delete, func, select
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
