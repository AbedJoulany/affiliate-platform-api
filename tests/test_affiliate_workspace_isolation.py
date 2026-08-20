"""Phase E Task 7 — join-campaign workspace isolation and global catalog regression."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import decode_access_token
from app.core.enums import WorkspaceMembershipRole
from app.core.workspace import WORKSPACE_ID_HEADER
from app.models.affiliate import Affiliate
from app.models.workspace import Workspace, WorkspaceMembership
from app.services.product_importer import ProductImporter
from tests.conftest import SessionLocal
from tests.test_api_endpoints import (
    API_PREFIX,
    auth_headers,
    create_affiliate_profile,
    create_product,
    register_and_login,
)
from tests.test_product_importer import _sample_data, _unique_product_id

JOIN = f"{API_PREFIX}/affiliates/join-campaign"
CAMPAIGNS = f"{API_PREFIX}/campaigns"
PRODUCTS = f"{API_PREFIX}/products"
QUEUES = f"{API_PREFIX}/queues"


def _headers(token: str, workspace_id: str | None = None) -> dict[str, str]:
    headers = auth_headers(token)
    if workspace_id is not None:
        headers[WORKSPACE_ID_HEADER] = workspace_id
    return headers


def _campaign_payload(name: str = "Join Campaign") -> dict:
    return {
        "name": name,
        "payout_amount": 25.0,
        "currency": "USD",
        "landing_url": "https://example.com/landing",
    }


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


async def _add_member(token: str, workspace_id: str) -> None:
    user_id = await _user_id_from_token(token)
    async with SessionLocal() as session:
        session.add(
            WorkspaceMembership(
                workspace_id=UUID(workspace_id),
                user_id=user_id,
                role=WorkspaceMembershipRole.MEMBER,
            )
        )
        await session.commit()


async def _create_campaign(client, token: str, workspace_id: str, **payload) -> dict:
    body = _campaign_payload()
    body.update(payload)
    response = await client.post(
        CAMPAIGNS,
        headers=_headers(token, workspace_id),
        json=body,
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _activate_campaign(client, token: str, workspace_id: str, campaign_id: str) -> dict:
    response = await client.patch(
        f"{CAMPAIGNS}/{campaign_id}",
        headers=_headers(token, workspace_id),
        json={"status": "active"},
    )
    assert response.status_code == 200, response.text
    return response.json()


async def _setup_member_affiliate(client, *, workspace_name: str):
    _, affiliate_token = await register_and_login(client, role="affiliate")
    _, advertiser_token = await register_and_login(client, role="advertiser")
    profile = await create_affiliate_profile(client, affiliate_token)
    workspace_id = await _create_workspace_for_user(advertiser_token, name=workspace_name)
    await _add_member(affiliate_token, workspace_id)
    campaign = await _create_campaign(client, advertiser_token, workspace_id)
    campaign = await _activate_campaign(
        client, advertiser_token, workspace_id, campaign["id"]
    )
    return affiliate_token, profile, campaign, workspace_id, advertiser_token


async def _seed_admin_affiliate(token: str) -> Affiliate:
    user_id = await _user_id_from_token(token)
    async with SessionLocal() as session:
        affiliate = Affiliate(
            user_id=user_id,
            referral_code=f"ADM{uuid4().hex[:7].upper()}",
        )
        session.add(affiliate)
        await session.commit()
        await session.refresh(affiliate)
        return affiliate


@pytest.mark.asyncio
async def test_unauthenticated_join_is_rejected(client):
    response = await client.post(JOIN, json={"campaign_id": str(uuid4())})
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


@pytest.mark.asyncio
async def test_missing_workspace_header_is_rejected(client):
    token, _profile, campaign, _workspace_id, _advertiser = await _setup_member_affiliate(
        client,
        workspace_name="Missing header",
    )
    response = await client.post(
        JOIN,
        headers=auth_headers(token),
        json={"campaign_id": campaign["id"]},
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Insufficient permissions"}


@pytest.mark.asyncio
async def test_malformed_workspace_header_is_rejected(client):
    token, _profile, campaign, _workspace_id, _advertiser = await _setup_member_affiliate(
        client,
        workspace_name="Malformed header",
    )
    response = await client.post(
        JOIN,
        headers=_headers(token, "not-a-uuid"),
        json={"campaign_id": campaign["id"]},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_unknown_workspace_header_is_rejected(client):
    token, _profile, campaign, _workspace_id, _advertiser = await _setup_member_affiliate(
        client,
        workspace_name="Unknown header",
    )
    response = await client.post(
        JOIN,
        headers=_headers(token, str(uuid4())),
        json={"campaign_id": campaign["id"]},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_non_member_workspace_header_is_rejected(client):
    token_a, _profile_a, campaign_a, _workspace_a, _adv_a = await _setup_member_affiliate(
        client,
        workspace_name="Member A",
    )
    _token_b, _profile_b, _campaign_b, workspace_b, _adv_b = await _setup_member_affiliate(
        client,
        workspace_name="Member B",
    )
    response = await client.post(
        JOIN,
        headers=_headers(token_a, workspace_b),
        json={"campaign_id": campaign_a["id"]},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_campaign_in_another_workspace_is_not_found(client):
    token_a, _profile_a, _campaign_a, workspace_a, _adv_a = await _setup_member_affiliate(
        client,
        workspace_name="Join A",
    )
    _token_b, _profile_b, campaign_b, _workspace_b, _adv_b = await _setup_member_affiliate(
        client,
        workspace_name="Join B",
    )
    response = await client.post(
        JOIN,
        headers=_headers(token_a, workspace_a),
        json={"campaign_id": campaign_b["id"]},
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Campaign not found"}
    assert campaign_b["id"] not in str(response.json())


@pytest.mark.asyncio
async def test_nonexistent_campaign_is_not_found(client):
    token, _profile, _campaign, workspace_id, _advertiser = await _setup_member_affiliate(
        client,
        workspace_name="Missing campaign",
    )
    missing_id = str(uuid4())
    response = await client.post(
        JOIN,
        headers=_headers(token, workspace_id),
        json={"campaign_id": missing_id},
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Campaign not found"}
    assert missing_id not in str(response.json())


@pytest.mark.asyncio
async def test_member_can_join_campaign_in_active_workspace(client):
    token, profile, campaign, workspace_id, _advertiser = await _setup_member_affiliate(
        client,
        workspace_name="Own join",
    )
    response = await client.post(
        JOIN,
        headers=_headers(token, workspace_id),
        json={"campaign_id": campaign["id"]},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["campaign_id"] == campaign["id"]
    assert body["affiliate_id"] == profile["id"]
    assert body["tracking_link"] == (
        f"{campaign['landing_url']}?ref={profile['referral_code']}&cid={campaign['id']}"
    )


@pytest.mark.asyncio
async def test_multi_workspace_user_is_scoped_to_header(client):
    _, affiliate_token = await register_and_login(client, role="affiliate")
    _, advertiser_token = await register_and_login(client, role="advertiser")
    profile = await create_affiliate_profile(client, affiliate_token)
    workspace_a = await _create_workspace_for_user(advertiser_token, name="Multi A")
    workspace_b = await _create_workspace_for_user(advertiser_token, name="Multi B")
    await _add_member(affiliate_token, workspace_a)
    await _add_member(affiliate_token, workspace_b)
    campaign_a = await _create_campaign(client, advertiser_token, workspace_a, name="Camp A")
    campaign_b = await _create_campaign(client, advertiser_token, workspace_b, name="Camp B")
    campaign_a = await _activate_campaign(client, advertiser_token, workspace_a, campaign_a["id"])
    campaign_b = await _activate_campaign(client, advertiser_token, workspace_b, campaign_b["id"])

    join_a = await client.post(
        JOIN,
        headers=_headers(affiliate_token, workspace_a),
        json={"campaign_id": campaign_a["id"]},
    )
    join_b = await client.post(
        JOIN,
        headers=_headers(affiliate_token, workspace_b),
        json={"campaign_id": campaign_b["id"]},
    )
    assert join_a.status_code == 201
    assert join_b.status_code == 201
    assert join_a.json()["affiliate_id"] == profile["id"]
    assert join_b.json()["affiliate_id"] == profile["id"]

    cross_a = await client.post(
        JOIN,
        headers=_headers(affiliate_token, workspace_a),
        json={"campaign_id": campaign_b["id"]},
    )
    cross_b = await client.post(
        JOIN,
        headers=_headers(affiliate_token, workspace_b),
        json={"campaign_id": campaign_a["id"]},
    )
    assert cross_a.status_code == 404
    assert cross_a.json() == {"detail": "Campaign not found"}
    assert cross_b.status_code == 404
    assert cross_b.json() == {"detail": "Campaign not found"}


@pytest.mark.asyncio
async def test_admin_can_join_without_membership(client):
    _token, _profile, campaign, workspace_id, _advertiser = await _setup_member_affiliate(
        client,
        workspace_name="Admin join",
    )
    _, admin_token = await register_and_login(client, role="admin")
    admin_affiliate = await _seed_admin_affiliate(admin_token)

    response = await client.post(
        JOIN,
        headers=_headers(admin_token, workspace_id),
        json={"campaign_id": campaign["id"]},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["campaign_id"] == campaign["id"]
    assert body["affiliate_id"] == str(admin_affiliate.id)
    assert f"ref={admin_affiliate.referral_code}" in body["tracking_link"]


@pytest.mark.asyncio
async def test_admin_missing_workspace_header_is_rejected(client):
    _token, _profile, campaign, _workspace_id, _advertiser = await _setup_member_affiliate(
        client,
        workspace_name="Admin missing header",
    )
    _, admin_token = await register_and_login(client, role="admin")
    await _seed_admin_affiliate(admin_token)

    response = await client.post(
        JOIN,
        headers=auth_headers(admin_token),
        json={"campaign_id": campaign["id"]},
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Insufficient permissions"}


@pytest.mark.asyncio
async def test_admin_cannot_join_campaign_from_another_workspace(client):
    _token_a, _profile_a, _campaign_a, workspace_a, _adv_a = await _setup_member_affiliate(
        client,
        workspace_name="Admin A",
    )
    _token_b, _profile_b, campaign_b, _workspace_b, _adv_b = await _setup_member_affiliate(
        client,
        workspace_name="Admin B",
    )
    _, admin_token = await register_and_login(client, role="admin")
    await _seed_admin_affiliate(admin_token)

    response = await client.post(
        JOIN,
        headers=_headers(admin_token, workspace_a),
        json={"campaign_id": campaign_b["id"]},
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Campaign not found"}
    assert campaign_b["id"] not in str(response.json())


@pytest.mark.asyncio
async def test_admin_unknown_workspace_is_rejected(client):
    _token, _profile, campaign, _workspace_id, _advertiser = await _setup_member_affiliate(
        client,
        workspace_name="Admin unknown",
    )
    _, admin_token = await register_and_login(client, role="admin")
    await _seed_admin_affiliate(admin_token)

    response = await client.post(
        JOIN,
        headers=_headers(admin_token, str(uuid4())),
        json={"campaign_id": campaign["id"]},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_inactive_campaign_is_rejected(client):
    token, _profile, _campaign, workspace_id, advertiser_token = await _setup_member_affiliate(
        client,
        workspace_name="Inactive campaign",
    )
    draft = await _create_campaign(client, advertiser_token, workspace_id, name="Draft")
    response = await client.post(
        JOIN,
        headers=_headers(token, workspace_id),
        json={"campaign_id": draft["id"]},
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "Campaign is not active"}


@pytest.mark.asyncio
async def test_duplicate_enrollment_is_rejected(client):
    token, _profile, campaign, workspace_id, _advertiser = await _setup_member_affiliate(
        client,
        workspace_name="Duplicate join",
    )
    first = await client.post(
        JOIN,
        headers=_headers(token, workspace_id),
        json={"campaign_id": campaign["id"]},
    )
    second = await client.post(
        JOIN,
        headers=_headers(token, workspace_id),
        json={"campaign_id": campaign["id"]},
    )
    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json() == {"detail": "Already joined this campaign"}


@pytest.mark.asyncio
async def test_products_remain_readable_without_workspace_header(client):
    response = await client.get(PRODUCTS)
    assert response.status_code == 200
    body = response.json()
    assert "items" in body
    assert "total" in body


@pytest.mark.asyncio
async def test_queue_can_attach_shared_product_from_any_workspace(client):
    _, admin_token = await register_and_login(client, role="admin")
    product = await create_product(client, admin_token)
    _, token_a = await register_and_login(client, role="affiliate")
    _, token_b = await register_and_login(client, role="affiliate")
    workspace_a = await _create_workspace_for_user(token_a, name="Catalog A")
    workspace_b = await _create_workspace_for_user(token_b, name="Catalog B")

    queue_a = await client.post(
        QUEUES,
        headers=_headers(token_a, workspace_a),
        json={"content": "Workspace A copy", "product_id": product["id"]},
    )
    queue_b = await client.post(
        QUEUES,
        headers=_headers(token_b, workspace_b),
        json={"content": "Workspace B copy", "product_id": product["id"]},
    )
    assert queue_a.status_code == 201, queue_a.text
    assert queue_b.status_code == 201, queue_b.text
    assert queue_a.json()["product_id"] == product["id"]
    assert queue_b.json()["product_id"] == product["id"]


@pytest.mark.asyncio
async def test_aliexpress_product_id_remains_globally_unique(
    session: AsyncSession,
):
    importer = ProductImporter(session)
    product_id = _unique_product_id()
    first = await importer.upsert_product(_sample_data(product_id))
    second = await importer.upsert_product(_sample_data(product_id))

    assert first.imported is True
    assert second.imported is False
    assert second.product.id == first.product.id
    assert second.product.aliexpress_product_id == product_id
    assert first.product.price == Decimal("29.99")
