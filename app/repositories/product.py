from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ProductStatus
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
