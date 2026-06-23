from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversion import Conversion
from app.repositories.base import BaseRepository


class ConversionRepository(BaseRepository[Conversion]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Conversion)

    async def get_by_external_order_id(self, external_order_id: str) -> Conversion | None:
        result = await self.session.execute(
            select(Conversion).where(Conversion.external_order_id == external_order_id)
        )
        return result.scalar_one_or_none()

    async def list_by_affiliate(
        self,
        affiliate_id: UUID,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Conversion]:
        result = await self.session.execute(
            select(Conversion)
            .where(Conversion.affiliate_id == affiliate_id)
            .offset(skip)
            .limit(limit)
            .order_by(Conversion.created_at.desc())
        )
        return list(result.scalars().all())
