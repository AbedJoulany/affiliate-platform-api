from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.factory import get_ai_provider
from app.ai.product_context import ProductContext
from app.ai.prompts import build_arabic_marketing_prompt
from app.ai.url_fetcher import ProductURLFetcher
from app.core.enums import AIProviderType
from app.repositories.product import ProductRepository
from app.schemas.ai_content import GenerateContentResponse
from app.services.exceptions import NotFoundError


class AIContentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.product_repo = ProductRepository(session)
        self.url_fetcher = ProductURLFetcher()

    async def generate_marketing_content(
        self,
        *,
        product_id: UUID | None = None,
        url: str | None = None,
        provider: AIProviderType | None = None,
    ) -> GenerateContentResponse:
        if product_id is not None:
            context = await self._context_from_product_id(product_id)
        else:
            context = await self._context_from_url(str(url))

        ai_provider = get_ai_provider(provider)
        prompt = build_arabic_marketing_prompt(context)
        content = await ai_provider.generate_content(prompt)

        return GenerateContentResponse(
            product_id=context.product_id,
            source_url=context.product_url if context.product_id is None else None,
            provider=AIProviderType(ai_provider.name),
            content=content,
        )

    async def _context_from_product_id(self, product_id: UUID) -> ProductContext:
        product = await self.product_repo.get_by_id(product_id)
        if not product:
            raise NotFoundError("Product not found")
        return ProductContext.from_product(product)

    async def _context_from_url(self, url: str) -> ProductContext:
        normalized_url = url.strip()

        existing = await self.product_repo.get_by_product_url(normalized_url)
        if existing:
            return ProductContext.from_product(existing)

        metadata = await self.url_fetcher.fetch(normalized_url)
        return ProductContext.from_url_metadata(
            url=metadata.url,
            title=metadata.title,
            description=metadata.description,
            image_url=metadata.image_url,
        )
