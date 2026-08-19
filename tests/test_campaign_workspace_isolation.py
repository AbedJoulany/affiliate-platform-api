"""Phase E Task 4 — campaign workspace isolation."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.auth.security import decode_access_token
from app.core.enums import WorkspaceMembershipRole
from app.core.workspace import WORKSPACE_ID_HEADER
from app.models.campaign import Campaign
from app.models.workspace import Workspace, WorkspaceMembership
from tests.conftest import SessionLocal
from tests.test_api_endpoints import (
    API_PREFIX,
    auth_headers,
    register_and_login,
    workspace_auth_headers,
)

CAMPAIGNS = f"{API_PREFIX}/campaigns"


def _campaign_payload(name: str = "Isolated Campaign", **extra) -> dict:
    body = {
        "name": name,
        "description": "Workspace isolation campaign",
        "payout_amount": 25.0,
        "currency": "USD",
        "landing_url": "https://example.com/landing",
    }
    body.update(extra)
    return body


def _headers(token: str, workspace_id: str | None = None) -> dict[str, str]:
    headers = auth_headers(token)
    if workspace_id is not None:
        headers[WORKSPACE_ID_HEADER] = workspace_id
    return headers


async def _user_id_from_token(token: str) -> UUID:
    return UUID(decode_access_token(token)["sub"])


async def _create_workspace_for_user(token: str, *, name: str) -> str:
    owner_id = await _user_id_from_token(token)
    async with SessionLocal() as session:
        workspace = Workspace(name=name, created_by_user_id=owner_id)
        session.add(workspace)
        await session.flush()
        session.add(
            WorkspaceMembership(
                workspace_id=workspace.id,
                user_id=owner_id,
                role=WorkspaceMembershipRole.OWNER,
            )
        )
        await session.commit()
        await session.refresh(workspace)
        return str(workspace.id)


async def _create_campaign(client, token: str, workspace_id: str, **payload) -> dict:
    response = await client.post(
        CAMPAIGNS,
        headers=_headers(token, workspace_id),
        json=_campaign_payload(**payload),
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_missing_workspace_header_is_rejected(client):
    _, token = await register_and_login(client, role="advertiser")
    response = await client.get(f"{CAMPAIGNS}/active", headers=auth_headers(token))
    assert response.status_code == 403
    assert response.json() == {"detail": "Insufficient permissions"}


@pytest.mark.asyncio
async def test_invalid_workspace_header_is_rejected(client):
    _, token = await register_and_login(client, role="advertiser")
    response = await client.get(
        f"{CAMPAIGNS}/active",
        headers=_headers(token, "not-a-uuid"),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_unknown_workspace_header_is_rejected(client):
    _, token = await register_and_login(client, role="advertiser")
    response = await client.get(
        f"{CAMPAIGNS}/active",
        headers=_headers(token, str(uuid4())),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_non_member_workspace_header_is_rejected(client):
    _, token_a = await register_and_login(client, role="advertiser")
    _, token_b = await register_and_login(client, role="advertiser")
    workspace_b = await _create_workspace_for_user(token_b, name="B only")

    response = await client.get(
        f"{CAMPAIGNS}/active",
        headers=_headers(token_a, workspace_b),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_valid_member_can_use_workspace(client):
    _, token = await register_and_login(client, role="advertiser")
    workspace_id = await _create_workspace_for_user(token, name="Member workspace")
    campaign = await _create_campaign(client, token, workspace_id, name="Owned")

    response = await client.get(
        f"{CAMPAIGNS}/{campaign['id']}",
        headers=_headers(token, workspace_id),
    )
    assert response.status_code == 200
    assert response.json()["id"] == campaign["id"]


@pytest.mark.asyncio
async def test_own_workspace_campaign_can_be_read(client):
    _, token = await register_and_login(client, role="advertiser")
    workspace_id = await _create_workspace_for_user(token, name="Read own")
    campaign = await _create_campaign(client, token, workspace_id)

    response = await client.get(
        f"{CAMPAIGNS}/{campaign['id']}",
        headers=_headers(token, workspace_id),
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Isolated Campaign"


@pytest.mark.asyncio
async def test_other_workspace_campaign_cannot_be_read(client):
    _, token_a = await register_and_login(client, role="advertiser")
    _, token_b = await register_and_login(client, role="advertiser")
    workspace_a = await _create_workspace_for_user(token_a, name="A")
    workspace_b = await _create_workspace_for_user(token_b, name="B")
    campaign_b = await _create_campaign(client, token_b, workspace_b, name="Secret B")

    response = await client.get(
        f"{CAMPAIGNS}/{campaign_b['id']}",
        headers=_headers(token_a, workspace_a),
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Campaign not found"}
    assert campaign_b["id"] not in str(response.json())


@pytest.mark.asyncio
async def test_list_returns_only_active_workspace_campaigns(client):
    _, token = await register_and_login(client, role="advertiser")
    workspace_a = await _create_workspace_for_user(token, name="List A")
    workspace_b = await _create_workspace_for_user(token, name="List B")
    campaign_a = await _create_campaign(client, token, workspace_a, name="In A")
    campaign_b = await _create_campaign(client, token, workspace_b, name="In B")

    await client.patch(
        f"{CAMPAIGNS}/{campaign_a['id']}",
        headers=_headers(token, workspace_a),
        json={"status": "active"},
    )
    await client.patch(
        f"{CAMPAIGNS}/{campaign_b['id']}",
        headers=_headers(token, workspace_b),
        json={"status": "active"},
    )

    list_a = await client.get(f"{CAMPAIGNS}/active", headers=_headers(token, workspace_a))
    list_b = await client.get(f"{CAMPAIGNS}/active", headers=_headers(token, workspace_b))
    ids_a = {item["id"] for item in list_a.json()}
    ids_b = {item["id"] for item in list_b.json()}

    assert campaign_a["id"] in ids_a
    assert campaign_b["id"] not in ids_a
    assert campaign_b["id"] in ids_b
    assert campaign_a["id"] not in ids_b


@pytest.mark.asyncio
async def test_active_campaign_endpoint_is_workspace_isolated(client):
    _, token_a = await register_and_login(client, role="advertiser")
    _, token_b = await register_and_login(client, role="advertiser")
    workspace_a = await _create_workspace_for_user(token_a, name="Active A")
    workspace_b = await _create_workspace_for_user(token_b, name="Active B")
    campaign_a = await _create_campaign(client, token_a, workspace_a, name="Active in A")
    await client.patch(
        f"{CAMPAIGNS}/{campaign_a['id']}",
        headers=_headers(token_a, workspace_a),
        json={"status": "active"},
    )

    response = await client.get(f"{CAMPAIGNS}/active", headers=_headers(token_b, workspace_b))
    assert response.status_code == 200
    assert campaign_a["id"] not in {item["id"] for item in response.json()}


@pytest.mark.asyncio
async def test_create_assigns_active_workspace_not_client_body(client):
    _, token = await register_and_login(client, role="advertiser")
    _, other_token = await register_and_login(client, role="advertiser")
    workspace_a = await _create_workspace_for_user(token, name="Create A")
    workspace_b = await _create_workspace_for_user(other_token, name="Create B")

    response = await client.post(
        CAMPAIGNS,
        headers=_headers(token, workspace_a),
        json=_campaign_payload(name="No client override", workspace_id=workspace_b),
    )
    assert response.status_code == 201
    campaign = response.json()
    assert "workspace_id" not in campaign

    own = await client.get(
        f"{CAMPAIGNS}/{campaign['id']}",
        headers=_headers(token, workspace_a),
    )
    other = await client.get(
        f"{CAMPAIGNS}/{campaign['id']}",
        headers=_headers(other_token, workspace_b),
    )
    assert own.status_code == 200
    assert other.status_code == 404


@pytest.mark.asyncio
async def test_own_workspace_update_succeeds_cross_workspace_update_fails(client):
    _, token_a = await register_and_login(client, role="advertiser")
    _, token_b = await register_and_login(client, role="advertiser")
    workspace_a = await _create_workspace_for_user(token_a, name="Update A")
    workspace_b = await _create_workspace_for_user(token_b, name="Update B")
    campaign_a = await _create_campaign(client, token_a, workspace_a)
    campaign_b = await _create_campaign(client, token_b, workspace_b)

    own = await client.patch(
        f"{CAMPAIGNS}/{campaign_a['id']}",
        headers=_headers(token_a, workspace_a),
        json={"description": "updated in A"},
    )
    assert own.status_code == 200
    assert own.json()["description"] == "updated in A"

    cross = await client.patch(
        f"{CAMPAIGNS}/{campaign_b['id']}",
        headers=_headers(token_a, workspace_a),
        json={"description": "hijack"},
    )
    assert cross.status_code == 404
    assert cross.json() == {"detail": "Campaign not found"}


@pytest.mark.asyncio
async def test_authenticated_user_cannot_update_another_users_campaign(client):
    _, owner_token = await register_and_login(client, role="advertiser")
    _, stranger_token = await register_and_login(client, role="affiliate")
    workspace = await _create_workspace_for_user(owner_token, name="Owner workspace")
    campaign = await _create_campaign(client, owner_token, workspace)

    stranger_own_workspace = await _create_workspace_for_user(
        stranger_token,
        name="Stranger workspace",
    )
    response = await client.patch(
        f"{CAMPAIGNS}/{campaign['id']}",
        headers=_headers(stranger_token, stranger_own_workspace),
        json={"description": "not allowed"},
    )
    assert response.status_code == 404

    still_unrelated = await client.patch(
        f"{CAMPAIGNS}/{campaign['id']}",
        headers=auth_headers(stranger_token),
        json={"description": "still not allowed"},
    )
    assert still_unrelated.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_operate_without_membership(client):
    _, owner_token = await register_and_login(client, role="advertiser")
    _, admin_token = await register_and_login(client, role="admin")
    workspace = await _create_workspace_for_user(owner_token, name="Admin target")
    campaign = await _create_campaign(client, owner_token, workspace)

    fetched = await client.get(
        f"{CAMPAIGNS}/{campaign['id']}",
        headers=_headers(admin_token, workspace),
    )
    assert fetched.status_code == 200

    updated = await client.patch(
        f"{CAMPAIGNS}/{campaign['id']}",
        headers=_headers(admin_token, workspace),
        json={"description": "admin update"},
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "admin update"

    listed = await client.get(CAMPAIGNS, headers=_headers(admin_token, workspace))
    assert listed.status_code == 200
    assert campaign["id"] in {item["id"] for item in listed.json()}


@pytest.mark.asyncio
async def test_admin_is_still_scoped_to_header_workspace(client):
    _, token_a = await register_and_login(client, role="advertiser")
    _, token_b = await register_and_login(client, role="advertiser")
    _, admin_token = await register_and_login(client, role="admin")
    workspace_a = await _create_workspace_for_user(token_a, name="Admin A")
    workspace_b = await _create_workspace_for_user(token_b, name="Admin B")
    campaign_b = await _create_campaign(client, token_b, workspace_b, name="B campaign")

    response = await client.get(
        f"{CAMPAIGNS}/{campaign_b['id']}",
        headers=_headers(admin_token, workspace_a),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_header_selects_workspace_for_user_with_multiple_memberships(client):
    _, token = await register_and_login(client, role="advertiser")
    workspace_a = await _create_workspace_for_user(token, name="Multi A")
    workspace_b = await _create_workspace_for_user(token, name="Multi B")
    campaign_a = await _create_campaign(client, token, workspace_a, name="A")
    campaign_b = await _create_campaign(client, token, workspace_b, name="B")

    fetched_a = await client.get(
        f"{CAMPAIGNS}/{campaign_a['id']}",
        headers=_headers(token, workspace_a),
    )
    fetched_b = await client.get(
        f"{CAMPAIGNS}/{campaign_b['id']}",
        headers=_headers(token, workspace_b),
    )
    wrong = await client.get(
        f"{CAMPAIGNS}/{campaign_b['id']}",
        headers=_headers(token, workspace_a),
    )
    assert fetched_a.status_code == 200
    assert fetched_b.status_code == 200
    assert wrong.status_code == 404


@pytest.mark.asyncio
async def test_cross_user_isolation_both_directions(client):
    _, token_a = await register_and_login(client, role="advertiser")
    _, token_b = await register_and_login(client, role="advertiser")
    workspace_a = await _create_workspace_for_user(token_a, name="User A")
    workspace_b = await _create_workspace_for_user(token_b, name="User B")
    campaign_a = await _create_campaign(client, token_a, workspace_a)
    campaign_b = await _create_campaign(client, token_b, workspace_b)

    a_reads_b = await client.get(
        f"{CAMPAIGNS}/{campaign_b['id']}",
        headers=_headers(token_a, workspace_a),
    )
    b_reads_a = await client.get(
        f"{CAMPAIGNS}/{campaign_a['id']}",
        headers=_headers(token_b, workspace_b),
    )
    assert a_reads_b.status_code == 404
    assert b_reads_a.status_code == 404


@pytest.mark.asyncio
async def test_unauthenticated_campaign_read_is_rejected(client):
    response = await client.get(f"{CAMPAIGNS}/active")
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


@pytest.mark.asyncio
async def test_campaign_has_no_delete_route(client):
    _, token = await register_and_login(client, role="advertiser")
    headers = await workspace_auth_headers(token)
    campaign = await _create_campaign(client, token, headers[WORKSPACE_ID_HEADER])
    response = await client.delete(
        f"{CAMPAIGNS}/{campaign['id']}",
        headers=headers,
    )
    assert response.status_code == 405


@pytest.mark.asyncio
async def test_created_campaign_workspace_id_matches_header(client):
    _, token = await register_and_login(client, role="advertiser")
    workspace_id = await _create_workspace_for_user(token, name="Persist workspace")
    campaign = await _create_campaign(client, token, workspace_id)

    async with SessionLocal() as session:
        stored = await session.get(Campaign, UUID(campaign["id"]))
        assert stored is not None
        assert str(stored.workspace_id) == workspace_id
