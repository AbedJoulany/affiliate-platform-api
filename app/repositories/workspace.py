from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workspace import Workspace, WorkspaceMembership
from app.repositories.base import BaseRepository


class WorkspaceRepository(BaseRepository[Workspace]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Workspace)

    async def create_workspace(self, workspace: Workspace) -> Workspace:
        return await self.create(workspace)

    async def list_for_user(self, user_id: UUID) -> list[Workspace]:
        result = await self.session.execute(
            select(Workspace)
            .join(WorkspaceMembership)
            .where(WorkspaceMembership.user_id == user_id)
            .order_by(Workspace.created_at.desc())
        )
        return list(result.scalars().all())


class WorkspaceMembershipRepository(BaseRepository[WorkspaceMembership]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, WorkspaceMembership)

    async def create_membership(
        self,
        membership: WorkspaceMembership,
    ) -> WorkspaceMembership:
        return await self.create(membership)

    async def get_membership(
        self,
        workspace_id: UUID,
        user_id: UUID,
    ) -> WorkspaceMembership | None:
        result = await self.session.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace_id,
                WorkspaceMembership.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()
