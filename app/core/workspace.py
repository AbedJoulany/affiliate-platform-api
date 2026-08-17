from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.auth.models import User
from app.core.database import get_db
from app.models.workspace import Workspace, WorkspaceMembership
from app.repositories.workspace import WorkspaceMembershipRepository, WorkspaceRepository
from app.services.exceptions import ForbiddenError

WORKSPACE_ID_HEADER = "X-Workspace-Id"


@dataclass(frozen=True, slots=True)
class WorkspaceContext:
    """Server-validated workspace authorization context for a single request."""

    user: User
    workspace: Workspace
    membership: WorkspaceMembership


def _parse_workspace_header(raw_workspace_id: str | None) -> UUID:
    """Treat the workspace header as untrusted input; never query on a malformed id."""
    if raw_workspace_id is None or not raw_workspace_id.strip():
        raise ForbiddenError()
    try:
        return UUID(raw_workspace_id.strip())
    except ValueError as exc:
        raise ForbiddenError() from exc


async def get_active_workspace(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    x_workspace_id: Annotated[str | None, Header(alias=WORKSPACE_ID_HEADER)] = None,
) -> WorkspaceContext:
    """Resolve `X-Workspace-Id` against a live `WorkspaceMembership` row.

    Authorization succeeds only when the workspace exists and the authenticated
    user has a corresponding membership. Missing, malformed, unknown, and
    non-member cases all raise ``ForbiddenError`` so the response does not
    disclose whether a workspace exists.
    """
    workspace_id = _parse_workspace_header(x_workspace_id)
    workspace = await WorkspaceRepository(db).get_by_id(workspace_id)
    membership = await WorkspaceMembershipRepository(db).get_membership(
        workspace_id,
        current_user.id,
    )
    if workspace is None or membership is None:
        raise ForbiddenError()
    return WorkspaceContext(
        user=current_user,
        workspace=workspace,
        membership=membership,
    )


ActiveWorkspace = Annotated[WorkspaceContext, Depends(get_active_workspace)]
