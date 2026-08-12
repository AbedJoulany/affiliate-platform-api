from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.aliexpress.client import AliExpressAffiliateClient
from app.aliexpress.types import DiscoveryMode, ProductSortOption
from app.core.config import Settings, get_settings
from app.models.aliexpress_category import AliExpressCategory
from app.repositories.product import AliExpressCategoryRepository
from app.schemas.discovery import ProductDiscoveryQuery
from app.services.product_discovery import ProductDiscoveryService
from app.services.product_importer import ProductImporter


class ProductDiscoveryPersistenceService:
    def __init__(
        self,
        session: AsyncSession,
        client: AliExpressAffiliateClient,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.importer = ProductImporter(session)
        self.discovery = ProductDiscoveryService(client, self.importer)
        self.client = client
        self.category_repo = AliExpressCategoryRepository(session)

    async def refresh_hot_products(self) -> dict:
        return await self._refresh_discovery_mode(DiscoveryMode.HOT)

    async def refresh_trending_products(self) -> dict:
        return await self._refresh_discovery_mode(DiscoveryMode.TRENDING)

    async def refresh_categories(self) -> dict:
        categories = await self.client.get_categories()

        models = [
            AliExpressCategory(
                category_id=int(item["category_id"]),
                category_name=str(item["category_name"]),
                parent_category_id=int(item.get("parent_category_id") or 0),
                synced_at=datetime.now(UTC),
            )
            for item in categories
            if item.get("category_id") is not None and item.get("category_name")
        ]
        count = await self.category_repo.replace_all(models)
        return {"synced_categories": count}

    async def _refresh_discovery_mode(self, mode: DiscoveryMode) -> dict:
        query = ProductDiscoveryQuery(
            mode=mode,
            sort=ProductSortOption.ORDERS_DESC,
            page=1,
            page_size=self.settings.aliexpress_discovery_refresh_batch_size,
            persist=True,
        )
        result = await self.discovery.discover(query)
        return {
            "mode": mode.value,
            "discovered": len(result.products),
            "persisted": result.response.persisted_count,
        }
