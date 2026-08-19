"""Phase E Task 5 — conversion workspace isolation."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.auth.security import decode_access_token
from app.core.enums import WorkspaceMembershipRole
from app.core.workspace import WORKSPACE_ID_HEADER
from app.models.workspace import Workspace, WorkspaceMembership
from tests.conftest import SessionLocal
from tests.test_api_endpoints import (
    API_PREFIX,
    activate_campaign,
    add_workspace_member,
    auth_headers,
    create_affiliate_profile,
    register_and_login,
)

CONVERSIONS = f"{API_PREFIX}/conversions"
CAMPAIGNS = f"{API_PREFIX}/campaigns"


def _headers(token: str, workspace_id: str | None = None) -> dict[str, str]:
    headers = auth_headers(token)
    if workspace_id is not None:
        headers[WORKSPACE_ID_HEADER] = workspace_id
    return headers


def _conversion_body(affiliate_id: str, campaign_id: str, **extra) -> dict:
    body = {
        "affiliate_id": affiliate_id,
        "campaign_id": campaign_id,
        "external_order_id": f"order-{uuid4().hex[:8]}",
        "amount": 125.50,
        "currency": "USD",
        "click_id": "click123",
    }
    body.update(extra)
    return body


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


async def _create_campaign(client, token: str, workspace_id: str) -> dict:
    response = await client.post(
        CAMPAIGNS,
        headers=_headers(token, workspace_id),
        json={
            "name": f"Campaign {uuid4().hex[:6]}",
            "payout_amount": 25.0,
            "currency": "USD",
            "landing_url": "https://example.com/landing",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _enroll(client, affiliate_token: str, campaign_id: str) -> None:
    join = await client.post(
        f"{API_PREFIX}/affiliates/join-campaign",
        headers=auth_headers(affiliate_token),
        json={"campaign_id": campaign_id},
    )
    assert join.status_code == 201, join.text


async def _setup_affiliate_workspace(client, *, workspace_name: str):
    _, affiliate_token = await register_and_login(client, role="affiliate")
    _, advertiser_token = await register_and_login(client, role="advertiser")
    profile = await create_affiliate_profile(client, affiliate_token)
    workspace_id = await _create_workspace_for_user(
        advertiser_token,
        name=workspace_name,
    )
    await add_workspace_member(affiliate_token, workspace_id)
    campaign = await _create_campaign(client, advertiser_token, workspace_id)
    campaign = await activate_campaign(client, advertiser_token, campaign["id"])
    await _enroll(client, affiliate_token, campaign["id"])
    return affiliate_token, profile, campaign, workspace_id


@pytest.mark.asyncio
async def test_missing_workspace_header_is_rejected(client):
    token, profile, campaign, _workspace_id = await _setup_affiliate_workspace(
        client,
        workspace_name="Missing header",
    )
    response = await client.post(
        CONVERSIONS,
        headers=auth_headers(token),
        json=_conversion_body(profile["id"], campaign["id"]),
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Insufficient permissions"}


@pytest.mark.asyncio
async def test_invalid_workspace_header_is_rejected(client):
    token, profile, campaign, _workspace_id = await _setup_affiliate_workspace(
        client,
        workspace_name="Invalid header",
    )
    response = await client.post(
        CONVERSIONS,
        headers=_headers(token, "not-a-uuid"),
        json=_conversion_body(profile["id"], campaign["id"]),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_unknown_workspace_header_is_rejected(client):
    token, profile, campaign, _workspace_id = await _setup_affiliate_workspace(
        client,
        workspace_name="Unknown header",
    )
    response = await client.post(
        CONVERSIONS,
        headers=_headers(token, str(uuid4())),
        json=_conversion_body(profile["id"], campaign["id"]),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_non_member_workspace_header_is_rejected(client):
    token_a, profile_a, campaign_a, workspace_a = await _setup_affiliate_workspace(
        client,
        workspace_name="A",
    )
    token_b, _profile_b, _campaign_b, workspace_b = await _setup_affiliate_workspace(
        client,
        workspace_name="B",
    )
    response = await client.post(
        CONVERSIONS,
        headers=_headers(token_a, workspace_b),
        json=_conversion_body(profile_a["id"], campaign_a["id"]),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_valid_member_can_create_and_list_own_workspace_conversion(client):
    token, profile, campaign, workspace_id = await _setup_affiliate_workspace(
        client,
        workspace_name="Own",
    )
    created = await client.post(
        CONVERSIONS,
        headers=_headers(token, workspace_id),
        json=_conversion_body(profile["id"], campaign["id"]),
    )
    assert created.status_code == 201
    conversion = created.json()

    listed = await client.get(f"{CONVERSIONS}/me", headers=_headers(token, workspace_id))
    assert listed.status_code == 200
    assert conversion["id"] in {item["id"] for item in listed.json()}


@pytest.mark.asyncio
async def test_cannot_read_other_workspace_conversions(client):
    token_a, profile_a, campaign_a, workspace_a = await _setup_affiliate_workspace(
        client,
        workspace_name="Read A",
    )
    token_b, profile_b, campaign_b, workspace_b = await _setup_affiliate_workspace(
        client,
        workspace_name="Read B",
    )
    created_b = await client.post(
        CONVERSIONS,
        headers=_headers(token_b, workspace_b),
        json=_conversion_body(profile_b["id"], campaign_b["id"]),
    )
    assert created_b.status_code == 201
    conversion_b = created_b.json()

    listed_a = await client.get(f"{CONVERSIONS}/me", headers=_headers(token_a, workspace_a))
    assert listed_a.status_code == 200
    assert conversion_b["id"] not in {item["id"] for item in listed_a.json()}


@pytest.mark.asyncio
async def test_list_me_is_scoped_to_header_workspace(client):
    _, affiliate_token = await register_and_login(client, role="affiliate")
    _, advertiser_token = await register_and_login(client, role="advertiser")
    profile = await create_affiliate_profile(client, affiliate_token)
    workspace_a = await _create_workspace_for_user(advertiser_token, name="Multi A")
    workspace_b = await _create_workspace_for_user(advertiser_token, name="Multi B")
    await add_workspace_member(affiliate_token, workspace_a)
    await add_workspace_member(affiliate_token, workspace_b)
    campaign_a = await _create_campaign(client, advertiser_token, workspace_a)
    campaign_b = await _create_campaign(client, advertiser_token, workspace_b)
    activate_a = await client.patch(
        f"{CAMPAIGNS}/{campaign_a['id']}",
        headers=_headers(advertiser_token, workspace_a),
        json={"status": "active"},
    )
    activate_b = await client.patch(
        f"{CAMPAIGNS}/{campaign_b['id']}",
        headers=_headers(advertiser_token, workspace_b),
        json={"status": "active"},
    )
    assert activate_a.status_code == 200
    assert activate_b.status_code == 200
    campaign_a = activate_a.json()
    campaign_b = activate_b.json()
    await _enroll(client, affiliate_token, campaign_a["id"])
    await _enroll(client, affiliate_token, campaign_b["id"])

    conv_a = await client.post(
        CONVERSIONS,
        headers=_headers(affiliate_token, workspace_a),
        json=_conversion_body(profile["id"], campaign_a["id"]),
    )
    conv_b = await client.post(
        CONVERSIONS,
        headers=_headers(affiliate_token, workspace_b),
        json=_conversion_body(profile["id"], campaign_b["id"]),
    )
    assert conv_a.status_code == 201
    assert conv_b.status_code == 201

    list_a = await client.get(
        f"{CONVERSIONS}/me",
        headers=_headers(affiliate_token, workspace_a),
    )
    list_b = await client.get(
        f"{CONVERSIONS}/me",
        headers=_headers(affiliate_token, workspace_b),
    )
    ids_a = {item["id"] for item in list_a.json()}
    ids_b = {item["id"] for item in list_b.json()}
    assert conv_a.json()["id"] in ids_a
    assert conv_b.json()["id"] not in ids_a
    assert conv_b.json()["id"] in ids_b
    assert conv_a.json()["id"] not in ids_b


@pytest.mark.asyncio
async def test_campaign_from_another_workspace_is_rejected(client):
    token_a, profile_a, _campaign_a, workspace_a = await _setup_affiliate_workspace(
        client,
        workspace_name="Create A",
    )
    _token_b, _profile_b, campaign_b, _workspace_b = await _setup_affiliate_workspace(
        client,
        workspace_name="Create B",
    )
    response = await client.post(
        CONVERSIONS,
        headers=_headers(token_a, workspace_a),
        json=_conversion_body(profile_a["id"], campaign_b["id"]),
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Campaign not found"}
    assert campaign_b["id"] not in str(response.json())


@pytest.mark.asyncio
async def test_cross_workspace_affiliate_campaign_combination_is_rejected(client):
    token_a, profile_a, campaign_a, workspace_a = await _setup_affiliate_workspace(
        client,
        workspace_name="Combo A",
    )
    token_b, profile_b, campaign_b, workspace_b = await _setup_affiliate_workspace(
        client,
        workspace_name="Combo B",
    )
    await _enroll(client, token_a, campaign_b["id"])

    _, admin_token = await register_and_login(client, role="admin")
    response = await client.post(
        CONVERSIONS,
        headers=_headers(admin_token, workspace_b),
        json=_conversion_body(profile_a["id"], campaign_b["id"]),
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Affiliate not found"}
    assert profile_a["id"] not in str(response.json())

    own_ok = await client.post(
        CONVERSIONS,
        headers=_headers(token_b, workspace_b),
        json=_conversion_body(profile_b["id"], campaign_b["id"]),
    )
    assert own_ok.status_code == 201


@pytest.mark.asyncio
async def test_client_cannot_override_workspace_via_payload(client):
    token, profile, campaign, workspace_id = await _setup_affiliate_workspace(
        client,
        workspace_name="No override",
    )
    _, other_token = await register_and_login(client, role="advertiser")
    other_workspace = await _create_workspace_for_user(other_token, name="Other")

    response = await client.post(
        CONVERSIONS,
        headers=_headers(token, workspace_id),
        json=_conversion_body(
            profile["id"],
            campaign["id"],
            workspace_id=other_workspace,
        ),
    )
    assert response.status_code == 201
    conversion = response.json()
    assert "workspace_id" not in conversion

    listed = await client.get(f"{CONVERSIONS}/me", headers=_headers(token, workspace_id))
    assert conversion["id"] in {item["id"] for item in listed.json()}
    other_list = await client.get(
        f"{CONVERSIONS}/me",
        headers=_headers(token, other_workspace),
    )
    assert other_list.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_create_and_update_without_membership(client):
    token, profile, campaign, workspace_id = await _setup_affiliate_workspace(
        client,
        workspace_name="Admin target",
    )
    created = await client.post(
        CONVERSIONS,
        headers=_headers(token, workspace_id),
        json=_conversion_body(profile["id"], campaign["id"]),
    )
    assert created.status_code == 201
    conversion_id = created.json()["id"]

    _, admin_token = await register_and_login(client, role="admin")
    listed = await client.get(CONVERSIONS, headers=_headers(admin_token, workspace_id))
    assert listed.status_code == 200
    assert conversion_id in {item["id"] for item in listed.json()}

    updated = await client.patch(
        f"{CONVERSIONS}/{conversion_id}",
        headers=_headers(admin_token, workspace_id),
        json={"status": "approved"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_admin_update_is_scoped_to_header_workspace(client):
    token_a, profile_a, campaign_a, workspace_a = await _setup_affiliate_workspace(
        client,
        workspace_name="Admin A",
    )
    _token_b, _profile_b, _campaign_b, workspace_b = await _setup_affiliate_workspace(
        client,
        workspace_name="Admin B",
    )
    created = await client.post(
        CONVERSIONS,
        headers=_headers(token_a, workspace_a),
        json=_conversion_body(profile_a["id"], campaign_a["id"]),
    )
    assert created.status_code == 201
    conversion_id = created.json()["id"]

    _, admin_token = await register_and_login(client, role="admin")
    response = await client.patch(
        f"{CONVERSIONS}/{conversion_id}",
        headers=_headers(admin_token, workspace_b),
        json={"status": "approved"},
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Conversion not found"}


@pytest.mark.asyncio
async def test_authenticated_user_cannot_access_another_users_workspace(client):
    token_a, profile_a, campaign_a, workspace_a = await _setup_affiliate_workspace(
        client,
        workspace_name="User A",
    )
    token_b, _profile_b, _campaign_b, workspace_b = await _setup_affiliate_workspace(
        client,
        workspace_name="User B",
    )
    created = await client.post(
        CONVERSIONS,
        headers=_headers(token_a, workspace_a),
        json=_conversion_body(profile_a["id"], campaign_a["id"]),
    )
    assert created.status_code == 201

    listed = await client.get(f"{CONVERSIONS}/me", headers=_headers(token_b, workspace_b))
    assert created.json()["id"] not in {item["id"] for item in listed.json()}

    stolen = await client.post(
        CONVERSIONS,
        headers=_headers(token_b, workspace_b),
        json=_conversion_body(profile_a["id"], campaign_a["id"]),
    )
    assert stolen.status_code == 403


@pytest.mark.asyncio
async def test_conversion_has_no_delete_route(client):
    token, profile, campaign, workspace_id = await _setup_affiliate_workspace(
        client,
        workspace_name="No delete",
    )
    created = await client.post(
        CONVERSIONS,
        headers=_headers(token, workspace_id),
        json=_conversion_body(profile["id"], campaign["id"]),
    )
    assert created.status_code == 201
    response = await client.delete(
        f"{CONVERSIONS}/{created.json()['id']}",
        headers=_headers(token, workspace_id),
    )
    assert response.status_code == 405
