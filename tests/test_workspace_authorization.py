"""Phase E Task 3 — workspace authorization dependency."""

from __future__ import annotations

from typing import Annotated
from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.auth.models import User
from app.auth.security import create_access_token, hash_password
from app.core.database import get_db
from app.core.enums import UserRole, WorkspaceMembershipRole
from app.core.workspace import (
    WORKSPACE_ID_HEADER,
    WorkspaceContext,
    get_active_workspace,
)
from app.main import service_error_handler
from app.models.workspace import Workspace, WorkspaceMembership
from app.repositories.workspace import WorkspaceMembershipRepository, WorkspaceRepository
from app.services.exceptions import ForbiddenError, ServiceError
from tests.conftest import override_get_db

PASSWORD = "test-password"


async def _create_user(
    session,
    *,
    email: str,
    role: UserRole = UserRole.USER,
) -> User:
    user = User(
        email=email,
        hashed_password=hash_password(PASSWORD),
        full_name="Workspace Auth Tester",
        role=role,
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _create_workspace(
    session,
    *,
    name: str,
    created_by_user_id=None,
) -> Workspace:
    return await WorkspaceRepository(session).create_workspace(
        Workspace(name=name, created_by_user_id=created_by_user_id),
    )


async def _create_membership(
    session,
    *,
    workspace: Workspace,
    user: User,
    role: WorkspaceMembershipRole = WorkspaceMembershipRole.MEMBER,
) -> WorkspaceMembership:
    return await WorkspaceMembershipRepository(session).create_membership(
        WorkspaceMembership(
            workspace_id=workspace.id,
            user_id=user.id,
            role=role,
        ),
    )


def _auth_headers(token: str, workspace_id: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if workspace_id is not None:
        headers[WORKSPACE_ID_HEADER] = workspace_id
    return headers


def _build_probe_app() -> FastAPI:
    probe = FastAPI()
    probe.add_exception_handler(ServiceError, service_error_handler)
    probe.dependency_overrides[get_db] = override_get_db

    @probe.get("/probe")
    async def probe_route(
        ctx: Annotated[WorkspaceContext, Depends(get_active_workspace)],
    ) -> dict[str, str]:
        return {
            "workspace_id": str(ctx.workspace.id),
            "membership_id": str(ctx.membership.id),
            "user_id": str(ctx.user.id),
        }

    return probe


@pytest.fixture
async def probe_client():
    transport = ASGITransport(app=_build_probe_app())
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_missing_header_is_rejected(session):
    user = await _create_user(session, email=f"missing-header-{uuid4().hex[:8]}@example.com")
    workspace = await _create_workspace(session, name="Only workspace", created_by_user_id=user.id)
    await _create_membership(session, workspace=workspace, user=user)

    with pytest.raises(ForbiddenError) as exc_info:
        await get_active_workspace(current_user=user, db=session, x_workspace_id=None)

    assert exc_info.value.status_code == 403
    assert exc_info.value.message == "Insufficient permissions"


@pytest.mark.asyncio
async def test_invalid_uuid_is_rejected_without_database_lookup(session, monkeypatch):
    user = await _create_user(session, email=f"invalid-uuid-{uuid4().hex[:8]}@example.com")
    looked_up = {"workspace": False, "membership": False}

    async def fail_get_by_id(self, entity_id):
        looked_up["workspace"] = True
        raise AssertionError("invalid UUID must not trigger a workspace lookup")

    async def fail_get_membership(self, workspace_id, user_id):
        looked_up["membership"] = True
        raise AssertionError("invalid UUID must not trigger a membership lookup")

    monkeypatch.setattr(WorkspaceRepository, "get_by_id", fail_get_by_id)
    monkeypatch.setattr(WorkspaceMembershipRepository, "get_membership", fail_get_membership)

    with pytest.raises(ForbiddenError) as exc_info:
        await get_active_workspace(
            current_user=user,
            db=session,
            x_workspace_id="not-a-uuid",
        )

    assert exc_info.value.status_code == 403
    assert looked_up == {"workspace": False, "membership": False}


@pytest.mark.asyncio
async def test_unknown_workspace_is_rejected(session):
    user = await _create_user(session, email=f"unknown-ws-{uuid4().hex[:8]}@example.com")

    with pytest.raises(ForbiddenError) as exc_info:
        await get_active_workspace(
            current_user=user,
            db=session,
            x_workspace_id=str(uuid4()),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.message == "Insufficient permissions"


@pytest.mark.asyncio
async def test_non_member_cannot_obtain_workspace_context(session):
    user_a = await _create_user(session, email=f"idor-a-{uuid4().hex[:8]}@example.com")
    user_b = await _create_user(session, email=f"idor-b-{uuid4().hex[:8]}@example.com")
    workspace_b = await _create_workspace(
        session,
        name="User B workspace",
        created_by_user_id=user_b.id,
    )
    await _create_membership(session, workspace=workspace_b, user=user_b)

    with pytest.raises(ForbiddenError) as exc_info:
        await get_active_workspace(
            current_user=user_a,
            db=session,
            x_workspace_id=str(workspace_b.id),
        )

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_valid_member_receives_validated_context(session):
    user = await _create_user(session, email=f"member-{uuid4().hex[:8]}@example.com")
    workspace = await _create_workspace(
        session,
        name="Member workspace",
        created_by_user_id=user.id,
    )
    membership = await _create_membership(
        session,
        workspace=workspace,
        user=user,
        role=WorkspaceMembershipRole.OWNER,
    )

    context = await get_active_workspace(
        current_user=user,
        db=session,
        x_workspace_id=str(workspace.id),
    )

    assert isinstance(context, WorkspaceContext)
    assert context.user.id == user.id
    assert context.workspace.id == workspace.id
    assert context.membership.id == membership.id
    assert context.membership.workspace_id == workspace.id
    assert context.membership.user_id == user.id


@pytest.mark.asyncio
async def test_header_selects_requested_workspace_among_multiple(session):
    user = await _create_user(session, email=f"multi-{uuid4().hex[:8]}@example.com")
    workspace_a = await _create_workspace(session, name="Workspace A", created_by_user_id=user.id)
    workspace_b = await _create_workspace(session, name="Workspace B", created_by_user_id=user.id)
    await _create_membership(session, workspace=workspace_a, user=user)
    await _create_membership(session, workspace=workspace_b, user=user)

    context_a = await get_active_workspace(
        current_user=user,
        db=session,
        x_workspace_id=str(workspace_a.id),
    )
    context_b = await get_active_workspace(
        current_user=user,
        db=session,
        x_workspace_id=str(workspace_b.id),
    )

    assert context_a.workspace.id == workspace_a.id
    assert context_b.workspace.id == workspace_b.id
    assert context_a.workspace.id != context_b.workspace.id


@pytest.mark.asyncio
async def test_cross_user_workspace_access_is_rejected(session):
    user_a = await _create_user(session, email=f"cross-a-{uuid4().hex[:8]}@example.com")
    user_b = await _create_user(session, email=f"cross-b-{uuid4().hex[:8]}@example.com")
    workspace_a = await _create_workspace(session, name="A", created_by_user_id=user_a.id)
    workspace_b = await _create_workspace(session, name="B", created_by_user_id=user_b.id)
    await _create_membership(session, workspace=workspace_a, user=user_a)
    await _create_membership(session, workspace=workspace_b, user=user_b)

    with pytest.raises(ForbiddenError):
        await get_active_workspace(
            current_user=user_a,
            db=session,
            x_workspace_id=str(workspace_b.id),
        )
    with pytest.raises(ForbiddenError):
        await get_active_workspace(
            current_user=user_b,
            db=session,
            x_workspace_id=str(workspace_a.id),
        )


@pytest.mark.asyncio
async def test_authorization_depends_on_membership_not_created_by(session):
    creator = await _create_user(session, email=f"creator-{uuid4().hex[:8]}@example.com")
    member = await _create_user(session, email=f"actual-member-{uuid4().hex[:8]}@example.com")
    workspace = await _create_workspace(
        session,
        name="Creator is not a member",
        created_by_user_id=creator.id,
    )
    membership = await _create_membership(session, workspace=workspace, user=member)

    with pytest.raises(ForbiddenError):
        await get_active_workspace(
            current_user=creator,
            db=session,
            x_workspace_id=str(workspace.id),
        )

    context = await get_active_workspace(
        current_user=member,
        db=session,
        x_workspace_id=str(workspace.id),
    )
    assert context.membership.id == membership.id
    assert context.user.id == member.id
    assert context.workspace.created_by_user_id == creator.id


@pytest.mark.asyncio
async def test_unauthenticated_request_is_rejected_by_existing_auth(probe_client):
    response = await probe_client.get("/probe", headers={WORKSPACE_ID_HEADER: str(uuid4())})

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


@pytest.mark.asyncio
async def test_no_implicit_workspace_when_user_has_exactly_one(session):
    user = await _create_user(session, email=f"single-{uuid4().hex[:8]}@example.com")
    workspace = await _create_workspace(
        session,
        name="The only workspace",
        created_by_user_id=user.id,
    )
    await _create_membership(session, workspace=workspace, user=user)

    with pytest.raises(ForbiddenError) as exc_info:
        await get_active_workspace(current_user=user, db=session, x_workspace_id=None)

    assert exc_info.value.status_code == 403

    with pytest.raises(ForbiddenError):
        await get_active_workspace(current_user=user, db=session, x_workspace_id="   ")


@pytest.mark.asyncio
async def test_http_missing_header_is_rejected_even_with_one_workspace(session, probe_client):
    user = await _create_user(session, email=f"http-missing-{uuid4().hex[:8]}@example.com")
    workspace = await _create_workspace(
        session,
        name="HTTP only workspace",
        created_by_user_id=user.id,
    )
    await _create_membership(session, workspace=workspace, user=user)
    await session.commit()

    token = create_access_token(user.id)
    response = await probe_client.get("/probe", headers=_auth_headers(token))

    assert response.status_code == 403
    assert response.json() == {"detail": "Insufficient permissions"}


@pytest.mark.asyncio
async def test_http_valid_member_probe_returns_validated_ids(session, probe_client):
    user = await _create_user(session, email=f"http-member-{uuid4().hex[:8]}@example.com")
    workspace = await _create_workspace(
        session,
        name="HTTP member workspace",
        created_by_user_id=user.id,
    )
    membership = await _create_membership(
        session,
        workspace=workspace,
        user=user,
        role=WorkspaceMembershipRole.OWNER,
    )
    await session.commit()

    token = create_access_token(user.id)
    response = await probe_client.get(
        "/probe",
        headers=_auth_headers(token, str(workspace.id)),
    )

    assert response.status_code == 200
    assert response.json() == {
        "workspace_id": str(workspace.id),
        "membership_id": str(membership.id),
        "user_id": str(user.id),
    }


@pytest.mark.asyncio
async def test_admin_role_does_not_bypass_membership(session):
    admin = await _create_user(
        session,
        email=f"admin-{uuid4().hex[:8]}@example.com",
        role=UserRole.ADMIN,
    )
    owner = await _create_user(session, email=f"owner-{uuid4().hex[:8]}@example.com")
    workspace = await _create_workspace(
        session,
        name="Not the admin's",
        created_by_user_id=owner.id,
    )
    await _create_membership(session, workspace=workspace, user=owner)

    with pytest.raises(ForbiddenError):
        await get_active_workspace(
            current_user=admin,
            db=session,
            x_workspace_id=str(workspace.id),
        )
