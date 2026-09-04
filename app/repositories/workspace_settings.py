from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workspace_settings import WorkspaceSettings
from app.repositories.base import BaseRepository


class WorkspaceSettingsRepository(BaseRepository[WorkspaceSettings]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, WorkspaceSettings)

    async def get_by_workspace_id(
        self,
        workspace_id: UUID,
    ) -> WorkspaceSettings | None:
        result = await self.session.execute(
            select(WorkspaceSettings).where(
                WorkspaceSettings.workspace_id == workspace_id
            )
        )
        return result.scalar_one_or_none()
