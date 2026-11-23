from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facebook_page import FacebookPage
from app.repositories.base import BaseRepository


class FacebookPageRepository(BaseRepository[FacebookPage]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, FacebookPage)

    async def get_in_workspace(
        self,
        page_id: UUID,
        workspace_id: UUID,
        *,
        for_update: bool = False,
    ) -> FacebookPage | None:
        statement = select(FacebookPage).where(
            FacebookPage.id == page_id,
            FacebookPage.workspace_id == workspace_id,
        )
        if for_update:
            statement = statement.with_for_update()
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_facebook_page_id(
        self, facebook_page_id: str, workspace_id: UUID
    ) -> FacebookPage | None:
        result = await self.session.execute(
            select(FacebookPage).where(
                FacebookPage.facebook_page_id == facebook_page_id,
                FacebookPage.workspace_id == workspace_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_in_workspace(self, workspace_id: UUID) -> list[FacebookPage]:
        result = await self.session.execute(
            select(FacebookPage)
            .where(FacebookPage.workspace_id == workspace_id)
            .order_by(FacebookPage.created_at.desc())
        )
        return list(result.scalars().all())
