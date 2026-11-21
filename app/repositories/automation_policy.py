from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.automation_policy import AutomationPolicy
from app.models.workspace import Workspace
from app.repositories.base import BaseRepository


class AutomationPolicyRepository(BaseRepository[AutomationPolicy]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AutomationPolicy)

    async def get_by_workspace_id(
        self,
        workspace_id: UUID,
        *,
        for_update: bool = False,
    ) -> AutomationPolicy | None:
        statement = select(AutomationPolicy).where(
            AutomationPolicy.workspace_id == workspace_id
        )
        if for_update:
            statement = statement.with_for_update()
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def lock_workspace(self, workspace_id: UUID) -> Workspace | None:
        result = await self.session.execute(
            select(Workspace)
            .where(Workspace.id == workspace_id)
            .with_for_update()
        )
        return result.scalar_one_or_none()
