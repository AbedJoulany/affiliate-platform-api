"""Shared API dependencies — auth dependencies are re-exported from app.auth."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, oauth2_scheme, require_roles
from app.core.database import get_db
from app.core.enums import UserRole
from app.core.workspace import WORKSPACE_ID_HEADER, get_active_workspace
from app.events.deps import get_event_publisher
from app.events.publisher import EventPublisher, NullEventPublisher
from app.models.user import User
from app.repositories.workspace import WorkspaceRepository
from app.services.exceptions import ForbiddenError
from app.services.queue import QueueService

__all__ = [
    "HttpWorkspaceId",
    "get_current_user",
    "get_http_workspace_id",
    "get_queue_service",
    "oauth2_scheme",
    "require_roles",
]


async def get_http_workspace_id(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_workspace_id: Annotated[str | None, Header(alias=WORKSPACE_ID_HEADER)] = None,
) -> UUID:
    """Resolve ``X-Workspace-Id`` for HTTP routes.

    Non-admins use Task 3 ``get_active_workspace``. Admins may name any existing
    workspace without a membership row, matching Tasks 4–5, while remaining
    scoped to that workspace.
    """
    if current_user.role == UserRole.ADMIN:
        if x_workspace_id is None or not x_workspace_id.strip():
            raise ForbiddenError()
        try:
            workspace_id = UUID(x_workspace_id.strip())
        except ValueError as exc:
            raise ForbiddenError() from exc
        workspace = await WorkspaceRepository(db).get_by_id(workspace_id)
        if workspace is None:
            raise ForbiddenError()
        return workspace.id
    ctx = await get_active_workspace(current_user, db, x_workspace_id)
    return ctx.workspace.id


HttpWorkspaceId = Annotated[UUID, Depends(get_http_workspace_id)]


def get_queue_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    events: Annotated[
        EventPublisher | NullEventPublisher, Depends(get_event_publisher)
    ],
) -> QueueService:
    """QueueService with the process EventPublisher (or Null outside lifespan)."""
    return QueueService(db, events=events)
