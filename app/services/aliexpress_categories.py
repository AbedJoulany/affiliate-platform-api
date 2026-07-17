from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.product import AliExpressCategoryRepository
from app.schemas.aliexpress import AliExpressCategoryListResponse


class AliExpressCategoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.category_repo = AliExpressCategoryRepository(session)

    async def list_cached(self) -> AliExpressCategoryListResponse:
        categories = await self.category_repo.list_all()
        synced_at = max((category.synced_at for category in categories), default=None)
        return AliExpressCategoryListResponse(
            items=categories,
            total=len(categories),
            synced_at=synced_at,
        )
