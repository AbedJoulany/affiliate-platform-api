from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ProductStatus, UserRole
from app.models.product import Product
from app.models.user import User
from app.repositories.product import ProductRepository
from app.schemas.product import ProductCreate, ProductListResponse, ProductUpdate
from app.services.exceptions import ForbiddenError, NotFoundError


class ProductService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.product_repo = ProductRepository(session)

    async def create(self, user: User, payload: ProductCreate) -> Product:
        self._ensure_admin(user)

        product = Product(
            title=payload.title,
            price=payload.price,
            discount=payload.discount,
            rating=payload.rating,
            sales=payload.sales,
            reviews=payload.reviews,
            image_url=str(payload.image_url),
            product_url=str(payload.product_url),
            score=payload.score,
            status=payload.status,
        )
        return await self.product_repo.create(product)

    async def get(self, product_id: UUID) -> Product:
        product = await self.product_repo.get_by_id(product_id)
        if not product:
            raise NotFoundError("Product not found")
        return product

    async def list_products(
        self,
        *,
        title: str | None = None,
        status: ProductStatus | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> ProductListResponse:
        items, total = await self.product_repo.search(
            title=title,
            status=status,
            skip=skip,
            limit=limit,
        )
        return ProductListResponse(items=items, total=total, skip=skip, limit=limit)

    async def update(self, user: User, product_id: UUID, payload: ProductUpdate) -> Product:
        self._ensure_admin(user)
        product = await self.get(product_id)

        update_data = payload.model_dump(exclude_unset=True)
        for url_field in ("image_url", "product_url"):
            if url_field in update_data and update_data[url_field] is not None:
                update_data[url_field] = str(update_data[url_field])

        for field, value in update_data.items():
            setattr(product, field, value)

        return await self.product_repo.update(product)

    async def delete(self, user: User, product_id: UUID) -> None:
        self._ensure_admin(user)
        product = await self.get(product_id)
        await self.product_repo.delete(product)

    def _ensure_admin(self, user: User) -> None:
        if user.role != UserRole.ADMIN:
            raise ForbiddenError("Only admins can manage products")
