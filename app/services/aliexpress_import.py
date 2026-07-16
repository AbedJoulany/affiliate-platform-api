from sqlalchemy.ext.asyncio import AsyncSession

from app.aliexpress.client import AliExpressAffiliateClient
from app.aliexpress.exceptions import AliExpressAPIError
from app.aliexpress.url_parser import AliExpressURLParser
from app.schemas.aliexpress import AliExpressImportResponse
from app.schemas.discovery import (
    ProductImportBatchRequest,
    ProductImportBatchResponse,
    ProductImportRequest,
    ProductImportResponse,
    ProductImportUrlRequest,
)
from app.services.exceptions import AliExpressAPIError as ServiceAliExpressAPIError
from app.services.exceptions import ValidationError
from app.services.product_importer import ProductImporter


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
        self.importer = ProductImporter(session, self.url_parser)

    async def import_product(
        self,
        *,
        url: str | None = None,
        product_id: str | None = None,
    ) -> AliExpressImportResponse:
        aliexpress_id = self._resolve_product_id(url=url, product_id=product_id)
        product_data = await self._fetch_product(aliexpress_id)
        # 2. Extract the long affiliate link from the raw API mapped schema object
        short_url = await self.client.generate_short_link(product_data.promotion_url)
        print(f"Generated short link for product {aliexpress_id}: {short_url}")
        product_data.promotion_url = short_url

        # 4. Proceed to upsert into the DB safely
        result = await self.importer.upsert_product(product_data)
        return AliExpressImportResponse(
            product=result.product,
            aliexpress_product_id=aliexpress_id,
            imported=result.imported,
            image_count=len(product_data.images),
        )

    async def import_from_url(self, payload: ProductImportUrlRequest) -> ProductImportResponse:
        result = await self.import_product(url=str(payload.url))
        return ProductImportResponse(
            product=result.product,
            aliexpress_product_id=result.aliexpress_product_id,
            imported=result.imported,
            image_count=result.image_count,
        )

    async def import_from_request(self, payload: ProductImportRequest) -> ProductImportResponse:
        result = await self.import_product(
            url=str(payload.url) if payload.url else None,
            product_id=payload.product_id,
        )
        return ProductImportResponse(
            product=result.product,
            aliexpress_product_id=result.aliexpress_product_id,
            imported=result.imported,
            image_count=result.image_count,
        )

    async def import_batch(self, payload: ProductImportBatchRequest) -> ProductImportBatchResponse:
        imported = 0
        updated = 0
        failed = 0
        products = []

        for product_id in payload.product_ids:
            try:
                result = await self.import_product(product_id=product_id.strip())
            except (ServiceAliExpressAPIError, ValidationError):
                failed += 1
                continue

            if result.imported:
                imported += 1
            else:
                updated += 1
            products.append(result.product)

        return ProductImportBatchResponse(
            imported=imported,
            updated=updated,
            failed=failed,
            products=products,
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

    async def _fetch_product(self, aliexpress_id: str):
        try:
            return await self.client.get_product_details(aliexpress_id)
        except AliExpressAPIError as exc:
            raise ServiceAliExpressAPIError(exc.message, code=exc.code) from exc
