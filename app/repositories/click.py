from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.click import Click
from app.repositories.base import BaseRepository


class ClickRepository(BaseRepository[Click]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Click)

    async def get_by_click_id(self, click_id: str) -> Click | None:
        result = await self.session.execute(select(Click).where(Click.click_id == click_id))
        return result.scalar_one_or_none()

    async def count_all(self) -> int:
        result = await self.session.execute(select(Click))
        return len(result.scalars().all())
