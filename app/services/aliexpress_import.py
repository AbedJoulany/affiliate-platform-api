from sqlalchemy.ext.asyncio import AsyncSession

from app.aliexpress.client import AliExpressAffiliateClient
from app.aliexpress.schemas import AliExpressProductData
from app.aliexpress.scoring import calculate_initial_product_score
from app.aliexpress.url_parser import AliExpressURLParser
from app.core.enums import ProductStatus
from app.models.product import Product
from app.repositories.product import ProductRepository
from app.schemas.aliexpress import AliExpressImportResponse
from app.services.exceptions import AliExpressAPIError as ServiceAliExpressAPIError
from app.services.exceptions import ValidationError
from app.aliexpress.client import AliExpressAPIError


class AliExpressImportService:
    def __init__(
        self,
        session: AsyncSession,
        client: AliExpressAffiliateClient,
        url_parser: AliExpressURLParser | None = None,
    ) -> None:
        self.session = session
        self.client = client
        self.url_parser = url_parser or AliExpressURLParser()
        self.product_repo = ProductRepository(session)

    async def import_product(
        self,
        *,
        url: str | None = None,
        product_id: str | None = None,
    ) -> AliExpressImportResponse:
        aliexpress_id = self._resolve_product_id(url=url, product_id=product_id)

        try:
            product_data = await self.client.get_product_details(aliexpress_id)
        except AliExpressAPIError as exc:
            raise ServiceAliExpressAPIError(exc.message, code=exc.code) from exc

        canonical_url = self.url_parser.build_product_url(aliexpress_id)
        existing = await self.product_repo.get_by_product_url(canonical_url)
        if existing is None and product_data.promotion_url:
            existing = await self.product_repo.get_by_product_url(product_data.promotion_url)

        if existing:
            product = await self._update_product(existing, product_data, canonical_url)
            imported = False
        else:
            product = await self._create_product(product_data, canonical_url)
            imported = True

        return AliExpressImportResponse(
            product=product,
            aliexpress_product_id=aliexpress_id,
            imported=imported,
            image_count=len(product_data.images),
        )

    def _resolve_product_id(
        self,
        *,
        url: str | None,
        product_id: str | None,
    ) -> str:
        if product_id:
            cleaned = product_id.strip()
            if not cleaned.isdigit():
                raise ValidationError("product_id must be a numeric AliExpress product ID")
            return cleaned
        try:
            return self.url_parser.extract_product_id(str(url))
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

    async def _create_product(
        self,
        data: AliExpressProductData,
        canonical_url: str,
    ) -> Product:
        product = Product(
            title=data.title,
            price=data.price,
            discount=data.discount,
            rating=data.rating,
            sales=data.sales,
            reviews=data.reviews,
            image_url=data.image_url,
            product_url=data.promotion_url or canonical_url,
            score=calculate_initial_product_score(
                rating=data.rating,
                sales=data.sales,
                discount=data.discount,
                reviews=data.reviews,
            ),
            status=ProductStatus.DRAFT,
        )
        return await self.product_repo.create(product)

    async def _update_product(
        self,
        product: Product,
        data: AliExpressProductData,
        canonical_url: str,
    ) -> Product:
        product.title = data.title
        product.price = data.price
        product.discount = data.discount
        product.rating = data.rating
        product.sales = data.sales
        product.reviews = data.reviews
        product.image_url = data.image_url
        product.product_url = data.promotion_url or canonical_url
        product.score = calculate_initial_product_score(
            rating=data.rating,
            sales=data.sales,
            discount=data.discount,
            reviews=data.reviews,
        )
        return await self.product_repo.update(product)
