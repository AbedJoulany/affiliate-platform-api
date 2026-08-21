"""GET /auth/me default_workspace_id and login EmailStr → 422."""

from __future__ import annotations

from uuid import UUID

import pytest

from app.auth.security import decode_access_token
from app.core.enums import WorkspaceMembershipRole
from app.core.workspace import WORKSPACE_ID_HEADER
from app.models.workspace import Workspace, WorkspaceMembership
from tests.conftest import SessionLocal
from tests.test_api_endpoints import (
    API_PREFIX,
    auth_headers,
    register_and_login,
    workspace_auth_headers,
)


async def _user_id(token: str) -> UUID:
    return UUID(decode_access_token(token)["sub"])


async def _add_workspace(token: str, *, name: str) -> str:
    user_id = await _user_id(token)
    async with SessionLocal() as session:
        workspace = Workspace(name=name, created_by_user_id=user_id)
        session.add(workspace)
        await session.flush()
        session.add(
            WorkspaceMembership(
                workspace_id=workspace.id,
                user_id=user_id,
                role=WorkspaceMembershipRole.OWNER,
            )
        )
        await session.commit()
        await session.refresh(workspace)
        return str(workspace.id)


@pytest.mark.asyncio
async def test_login_invalid_email_returns_422_not_500(client):
    response = await client.post(
        f"{API_PREFIX}/auth/login",
        data={"username": "admin@localhost", "password": "whatever1"},
    )
    assert response.status_code == 422
    assert response.status_code != 500
    assert "detail" in response.json()


@pytest.mark.asyncio
async def test_login_malformed_email_returns_422(client):
    response = await client.post(
        f"{API_PREFIX}/auth/login",
        data={"username": "not-an-email", "password": "whatever1"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_me_default_workspace_id_when_exactly_one_membership(client):
    _, token = await register_and_login(client, role="affiliate")
    workspace_id = await _add_workspace(token, name="Only Workspace")

    response = await client.get(f"{API_PREFIX}/auth/me", headers=auth_headers(token))
    assert response.status_code == 200
    assert response.json()["default_workspace_id"] == workspace_id


@pytest.mark.asyncio
async def test_me_default_workspace_id_null_when_zero_memberships(client):
    _, token = await register_and_login(client, role="affiliate")
    response = await client.get(f"{API_PREFIX}/auth/me", headers=auth_headers(token))
    assert response.status_code == 200
    assert response.json()["default_workspace_id"] is None


@pytest.mark.asyncio
async def test_me_default_workspace_id_null_when_multiple_memberships(client):
    _, token = await register_and_login(client, role="affiliate")
    await _add_workspace(token, name="Workspace A")
    await _add_workspace(token, name="Workspace B")

    response = await client.get(f"{API_PREFIX}/auth/me", headers=auth_headers(token))
    assert response.status_code == 200
    assert response.json()["default_workspace_id"] is None


@pytest.mark.asyncio
async def test_admin_default_workspace_id_follows_membership_count_not_role(client):
    _, admin_token = await register_and_login(client, role="admin")
    me = await client.get(f"{API_PREFIX}/auth/me", headers=auth_headers(admin_token))
    assert me.status_code == 200
    assert me.json()["default_workspace_id"] is None

    workspace_id = await _add_workspace(admin_token, name="Admin Sole")
    me_after = await client.get(f"{API_PREFIX}/auth/me", headers=auth_headers(admin_token))
    assert me_after.json()["default_workspace_id"] == workspace_id


@pytest.mark.asyncio
async def test_tenant_dashboard_still_requires_workspace_header(client):
    _, token = await register_and_login(client, role="affiliate")
    await _add_workspace(token, name="Dash")
    missing = await client.get(f"{API_PREFIX}/dashboard", headers=auth_headers(token))
    assert missing.status_code == 403


@pytest.mark.asyncio
async def test_non_member_cannot_use_another_workspace(client):
    _, owner_token = await register_and_login(client, role="affiliate")
    _, stranger_token = await register_and_login(client, role="affiliate")
    workspace_id = await _add_workspace(owner_token, name="Private")
    response = await client.get(
        f"{API_PREFIX}/dashboard",
        headers={**auth_headers(stranger_token), WORKSPACE_ID_HEADER: workspace_id},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_without_membership_can_use_existing_workspace_header(client):
    _, owner_token = await register_and_login(client, role="affiliate")
    _, admin_token = await register_and_login(client, role="admin")
    headers = await workspace_auth_headers(owner_token)
    workspace_id = headers[WORKSPACE_ID_HEADER]

    listed = await client.get(
        f"{API_PREFIX}/queues",
        headers={**auth_headers(admin_token), WORKSPACE_ID_HEADER: workspace_id},
    )
    assert listed.status_code == 200
    missing = await client.get(f"{API_PREFIX}/queues", headers=auth_headers(admin_token))
    assert missing.status_code == 403
