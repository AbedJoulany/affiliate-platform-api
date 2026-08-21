from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.auth.security import decode_access_token
from app.core.enums import WorkspaceMembershipRole
from app.core.workspace import WORKSPACE_ID_HEADER
from app.models.workspace import Workspace, WorkspaceMembership
from app.schemas.aliexpress import AliExpressImportResponse
from tests.conftest import SessionLocal, provision_test_user

API_PREFIX = "/api/v1"
PASSWORD = "StrongP@ssw0rd"


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def workspace_auth_headers(token: str) -> dict[str, str]:
    """Bearer token plus a live workspace membership for campaign isolation."""
    user_id = UUID(decode_access_token(token)["sub"])
    async with SessionLocal() as session:
        result = await session.execute(
            select(WorkspaceMembership).where(WorkspaceMembership.user_id == user_id)
        )
        membership = result.scalars().first()
        if membership is None:
            workspace = Workspace(name="Test Workspace", created_by_user_id=user_id)
            session.add(workspace)
            await session.flush()
            membership = WorkspaceMembership(
                workspace_id=workspace.id,
                user_id=user_id,
                role=WorkspaceMembershipRole.OWNER,
            )
            session.add(membership)
            await session.commit()
            await session.refresh(membership)
        return {
            **auth_headers(token),
            WORKSPACE_ID_HEADER: str(membership.workspace_id),
        }


async def campaign_workspace_id(campaign_id: str) -> str:
    from app.models.campaign import Campaign

    async with SessionLocal() as session:
        campaign = await session.get(Campaign, UUID(campaign_id))
        assert campaign is not None
        assert campaign.workspace_id is not None
        return str(campaign.workspace_id)


async def add_workspace_member(token: str, workspace_id: str) -> None:
    user_id = UUID(decode_access_token(token)["sub"])
    async with SessionLocal() as session:
        result = await session.execute(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == UUID(workspace_id),
                WorkspaceMembership.user_id == user_id,
            )
        )
        if result.scalar_one_or_none() is not None:
            return
        session.add(
            WorkspaceMembership(
                workspace_id=UUID(workspace_id),
                user_id=user_id,
                role=WorkspaceMembershipRole.MEMBER,
            )
        )
        await session.commit()


async def conversion_auth_headers(token: str, campaign_id: str) -> dict[str, str]:
    workspace_id = await campaign_workspace_id(campaign_id)
    await add_workspace_member(token, workspace_id)
    return {
        **auth_headers(token),
        WORKSPACE_ID_HEADER: workspace_id,
    }


async def join_campaign(client, token: str, campaign_id: str):
    """Enroll the caller's affiliate in a campaign using its workspace header."""
    headers = await conversion_auth_headers(token, campaign_id)
    return await client.post(
        f"{API_PREFIX}/affiliates/join-campaign",
        headers=headers,
        json={"campaign_id": campaign_id},
    )


@pytest.mark.asyncio
async def test_public_registration_always_creates_affiliate_and_rejects_role(client):
    email = f"public-{uuid4().hex[:8]}@example.com"
    response = await client.post(
        f"{API_PREFIX}/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "full_name": "Public User",
        },
    )
    assert response.status_code == 201
    assert response.json()["role"] == "affiliate"

    for role in ("admin", "advertiser"):
        privileged_response = await client.post(
            f"{API_PREFIX}/auth/register",
            json={
                "email": f"{role}-attempt-{uuid4().hex[:8]}@example.com",
                "password": PASSWORD,
                "full_name": f"{role.title()} Attempt",
                "role": role,
            },
        )
        assert privileged_response.status_code == 422


async def register_and_login(client, role: str = "affiliate") -> tuple[str, str]:
    email = f"test-{role}-{uuid4().hex[:6]}@example.com"
    await provision_test_user(
        email=email,
        password=PASSWORD,
        full_name=f"Test {role.title()}",
        role=role,
    )
    login_resp = await client.post(
        f"{API_PREFIX}/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    assert login_resp.status_code == 200
    return email, login_resp.json()["access_token"]


async def create_product(client, token: str) -> dict:
    payload = {
        "title": "Test Product",
        "price": 19.99,
        "discount": 0.0,
        "rating": 4.5,
        "sales": 100,
        "reviews": 25,
        "image_url": "https://example.com/image.png",
        "product_url": "https://example.com/product",
        "score": 8.5,
        "status": "active",
    }
    response = await client.post(
        f"{API_PREFIX}/products",
        headers=auth_headers(token),
        json=payload,
    )
    assert response.status_code == 201
    return response.json()


async def create_campaign(client, token: str) -> dict:
    payload = {
        "name": "Test Campaign",
        "description": "A campaign used by tests",
        "payout_amount": 25.0,
        "currency": "USD",
        "landing_url": "https://example.com/landing",
        "starts_at": datetime.now(UTC).isoformat(),
        "ends_at": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
    }
    response = await client.post(
        f"{API_PREFIX}/campaigns",
        headers=await workspace_auth_headers(token),
        json=payload,
    )
    assert response.status_code == 201
    return response.json()


async def activate_campaign(client, token: str, campaign_id: str) -> dict:
    response = await client.patch(
        f"{API_PREFIX}/campaigns/{campaign_id}",
        headers=await workspace_auth_headers(token),
        json={"status": "active"},
    )
    assert response.status_code == 200
    return response.json()


async def create_affiliate_profile(client, token: str) -> dict:
    payload = {
        "company_name": "Test Affiliate Co.",
        "website": "https://affiliate.example.com",
        "payout_details": "Bank transfer",
    }
    response = await client.post(
        f"{API_PREFIX}/affiliates",
        headers=auth_headers(token),
        json=payload,
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.asyncio
async def test_auth_register_login_and_profile_endpoints(client):
    _, token = await register_and_login(client, role="affiliate")

    response = await client.get(f"{API_PREFIX}/auth/me", headers=auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["email"].endswith("@example.com")
    assert body["role"] == "affiliate"
    assert body["is_active"] is True
    assert body["default_workspace_id"] is None

    response = await client.post(
        f"{API_PREFIX}/auth/register",
        json={
            "email": body["email"],
            "password": PASSWORD,
            "full_name": "Duplicate User",
        },
    )
    assert response.status_code == 409

    invalid_login = await client.post(
        f"{API_PREFIX}/auth/login",
        data={"username": "missing@example.com", "password": "wrong"},
    )
    assert invalid_login.status_code == 401


@pytest.mark.asyncio
async def test_affiliate_profile_crud_and_admin_listing(client):
    _, admin_token = await register_and_login(client, role="admin")
    _, affiliate_token = await register_and_login(client, role="affiliate")

    unauth_resp = await client.get(f"{API_PREFIX}/affiliates/me")
    assert unauth_resp.status_code == 401

    profile_resp = await client.post(
        f"{API_PREFIX}/affiliates",
        headers=auth_headers(affiliate_token),
        json={
            "company_name": "Affiliate Test",
            "website": "https://test.example.com",
            "payout_details": "PayPal",
        },
    )
    assert profile_resp.status_code == 201
    affiliate_profile = profile_resp.json()
    assert affiliate_profile["user_id"]
    assert affiliate_profile["referral_code"]
    assert affiliate_profile["status"] == "pending"

    update_resp = await client.patch(
        f"{API_PREFIX}/affiliates/{affiliate_profile['id']}",
        headers=auth_headers(affiliate_token),
        json={"company_name": "Affiliate Updated"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["company_name"] == "Affiliate Updated"

    for privileged_update in (
        {"status": "active"},
        {"commission_rate": 25},
    ):
        forbidden_update = await client.patch(
            f"{API_PREFIX}/affiliates/{affiliate_profile['id']}",
            headers=auth_headers(affiliate_token),
            json=privileged_update,
        )
        assert forbidden_update.status_code == 403

    admin_update = await client.patch(
        f"{API_PREFIX}/affiliates/{affiliate_profile['id']}",
        headers=auth_headers(admin_token),
        json={"status": "active", "commission_rate": 17.5},
    )
    assert admin_update.status_code == 200
    assert admin_update.json()["status"] == "active"
    assert float(admin_update.json()["commission_rate"]) == 17.5

    list_resp = await client.get(
        f"{API_PREFIX}/affiliates",
        headers=auth_headers(admin_token),
    )
    assert list_resp.status_code == 200
    assert any(item["id"] == affiliate_profile["id"] for item in list_resp.json())

    forbidden_resp = await client.get(
        f"{API_PREFIX}/affiliates",
        headers=auth_headers(affiliate_token),
    )
    assert forbidden_resp.status_code == 403


@pytest.mark.asyncio
async def test_affiliate_join_campaign_workflow(client):
    _, admin_token = await register_and_login(client, role="admin")
    _, affiliate_token = await register_and_login(client, role="affiliate")

    await create_affiliate_profile(client, affiliate_token)
    campaign = await create_campaign(client, admin_token)
    campaign = await activate_campaign(client, admin_token, campaign["id"])

    join_resp = await join_campaign(client, affiliate_token, campaign["id"])
    assert join_resp.status_code == 201
    assert join_resp.json()["campaign_id"] == campaign["id"]
    assert "tracking_link" in join_resp.json()

    duplicate_resp = await join_campaign(client, affiliate_token, campaign["id"])
    assert duplicate_resp.status_code == 409


@pytest.mark.asyncio
async def test_campaign_endpoints_with_role_based_access(client):
    _, admin_token = await register_and_login(client, role="admin")
    _, advertiser_token = await register_and_login(client, role="advertiser")
    _, affiliate_token = await register_and_login(client, role="affiliate")

    admin_campaign = await create_campaign(client, admin_token)
    advertiser_campaign = await create_campaign(client, advertiser_token)

    denied_resp = await client.post(
        f"{API_PREFIX}/campaigns",
        headers=await workspace_auth_headers(affiliate_token),
        json={
            "name": "Forbidden Campaign",
            "landing_url": "https://example.com",
            "payout_amount": 5.0,
            "currency": "USD",
        },
    )
    assert denied_resp.status_code == 403

    active_campaign = await activate_campaign(client, admin_token, admin_campaign["id"])
    assert active_campaign["status"] == "active"

    admin_headers = await workspace_auth_headers(admin_token)
    advertiser_headers = await workspace_auth_headers(advertiser_token)

    active_list = await client.get(f"{API_PREFIX}/campaigns/active", headers=admin_headers)
    assert active_list.status_code == 200
    assert any(item["id"] == admin_campaign["id"] for item in active_list.json())

    fetch_resp = await client.get(
        f"{API_PREFIX}/campaigns/{admin_campaign['id']}",
        headers=admin_headers,
    )
    assert fetch_resp.status_code == 200
    assert fetch_resp.json()["id"] == admin_campaign["id"]

    admin_list_resp = await client.get(
        f"{API_PREFIX}/campaigns",
        headers=admin_headers,
    )
    assert admin_list_resp.status_code == 200
    admin_list_ids = {item["id"] for item in admin_list_resp.json()}
    assert admin_campaign["id"] in admin_list_ids
    assert advertiser_campaign["id"] not in admin_list_ids

    forbidden_list = await client.get(
        f"{API_PREFIX}/campaigns",
        headers=await workspace_auth_headers(affiliate_token),
    )
    assert forbidden_list.status_code == 403

    update_resp = await client.patch(
        f"{API_PREFIX}/campaigns/{advertiser_campaign['id']}",
        headers=advertiser_headers,
        json={"description": "Updated by advertiser"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["description"] == "Updated by advertiser"


@pytest.mark.asyncio
async def test_conversion_endpoints_and_admin_status_update(client):
    _, admin_token = await register_and_login(client, role="admin")
    _, affiliate_token = await register_and_login(client, role="affiliate")

    affiliate_profile = await create_affiliate_profile(client, affiliate_token)
    campaign = await create_campaign(client, admin_token)
    campaign = await activate_campaign(client, admin_token, campaign["id"])

    join_resp = await join_campaign(client, affiliate_token, campaign["id"])
    assert join_resp.status_code == 201

    conversion_headers = await conversion_auth_headers(affiliate_token, campaign["id"])
    conversion_resp = await client.post(
        f"{API_PREFIX}/conversions",
        headers=conversion_headers,
        json={
            "affiliate_id": affiliate_profile["id"],
            "campaign_id": campaign["id"],
            "external_order_id": f"order-{uuid4().hex[:8]}",
            "amount": 125.50,
            "currency": "USD",
            "click_id": "click123",
        },
    )
    assert conversion_resp.status_code == 201
    conversion = conversion_resp.json()
    assert conversion["status"] == "pending"

    duplicate_resp = await client.post(
        f"{API_PREFIX}/conversions",
        headers=conversion_headers,
        json={
            "affiliate_id": affiliate_profile["id"],
            "campaign_id": campaign["id"],
            "external_order_id": conversion["external_order_id"],
            "amount": 125.50,
            "currency": "USD",
        },
    )
    assert duplicate_resp.status_code == 409

    me_resp = await client.get(
        f"{API_PREFIX}/conversions/me",
        headers=conversion_headers,
    )
    assert me_resp.status_code == 200
    assert any(item["id"] == conversion["id"] for item in me_resp.json())

    admin_headers = {
        **auth_headers(admin_token),
        WORKSPACE_ID_HEADER: conversion_headers[WORKSPACE_ID_HEADER],
    }
    admin_list_resp = await client.get(
        f"{API_PREFIX}/conversions",
        headers=admin_headers,
    )
    assert admin_list_resp.status_code == 200
    assert any(item["id"] == conversion["id"] for item in admin_list_resp.json())

    status_resp = await client.patch(
        f"{API_PREFIX}/conversions/{conversion['id']}",
        headers=admin_headers,
        json={"status": "approved"},
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "approved"

    forbidden_update = await client.patch(
        f"{API_PREFIX}/conversions/{conversion['id']}",
        headers=conversion_headers,
        json={"status": "paid"},
    )
    assert forbidden_update.status_code == 403


@pytest.mark.asyncio
async def test_product_crud_and_search_filters(client):
    _, admin_token = await register_and_login(client, role="admin")
    _, affiliate_token = await register_and_login(client, role="affiliate")

    product = await create_product(client, admin_token)

    list_resp = await client.get(f"{API_PREFIX}/products")
    assert list_resp.status_code == 200
    assert any(item["id"] == product["id"] for item in list_resp.json()["items"])

    search_resp = await client.get(f"{API_PREFIX}/products", params={"title": "Test Product"})
    assert search_resp.status_code == 200
    assert search_resp.json()["total"] >= 1

    get_resp = await client.get(f"{API_PREFIX}/products/{product['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["title"] == "Test Product"

    update_resp = await client.patch(
        f"{API_PREFIX}/products/{product['id']}",
        headers=auth_headers(admin_token),
        json={"price": 29.99},
    )
    assert update_resp.status_code == 200
    assert float(update_resp.json()["price"]) == 29.99

    delete_resp = await client.delete(
        f"{API_PREFIX}/products/{product['id']}",
        headers=auth_headers(admin_token),
    )
    assert delete_resp.status_code == 200
    assert delete_resp.json()["message"] == "Product deleted successfully"

    missing_resp = await client.get(f"{API_PREFIX}/products/{product['id']}")
    assert missing_resp.status_code == 404

    forbidden_resp = await client.post(
        f"{API_PREFIX}/products",
        headers=auth_headers(affiliate_token),
        json={
            "title": "Invalid Product",
            "price": 5.0,
            "image_url": "https://example.com/img.png",
            "product_url": "https://example.com/product",
        },
    )
    assert forbidden_resp.status_code == 403


@pytest.mark.asyncio
async def test_telegram_channel_crud_and_auth(client, mock_telegram_permissions):
    _, token = await register_and_login(client, role="affiliate")
    headers = await workspace_auth_headers(token)

    create_resp = await client.post(
        f"{API_PREFIX}/channels",
        headers=headers,
        json={"telegram_channel_id": "@testchannel", "title": "Test Channel"},
    )
    assert create_resp.status_code == 201
    channel = create_resp.json()
    assert channel["telegram_channel_id"] == "@testchannel"

    list_resp = await client.get(
        f"{API_PREFIX}/channels",
        headers=headers,
    )
    assert list_resp.status_code == 200
    assert any(item["id"] == channel["id"] for item in list_resp.json()["items"])

    update_resp = await client.put(
        f"{API_PREFIX}/channels/{channel['id']}",
        headers=headers,
        json={"title": "Updated Channel"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["title"] == "Updated Channel"

    delete_resp = await client.delete(
        f"{API_PREFIX}/channels/{channel['id']}",
        headers=headers,
    )
    assert delete_resp.status_code == 200
    assert delete_resp.json()["message"] == "Channel deleted successfully"

    unauth_resp = await client.post(
        f"{API_PREFIX}/channels",
        json={"telegram_channel_id": "@testchannel2", "title": "No Auth"},
    )
    assert unauth_resp.status_code == 401


@pytest.mark.asyncio
async def test_ai_content_generation_with_product_and_url(client, mock_ai_provider):
    _, token = await register_and_login(client, role="affiliate")

    admin_email, admin_token = await register_and_login(client, role="admin")
    product = await create_product(client, admin_token)

    response = await client.post(
        f"{API_PREFIX}/ai-content/generate",
        headers=auth_headers(token),
        json={"product_id": product["id"]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "openai"
    assert body["product_id"] == product["id"]
    assert "نص" in body["content"]

    url_response = await client.post(
        f"{API_PREFIX}/ai-content/generate",
        headers=auth_headers(token),
        json={"url": "https://example.com/other-product"},
    )
    assert url_response.status_code == 200
    assert url_response.json()["source_url"] == "https://example.com/other-product"

    invalid_response = await client.post(
        f"{API_PREFIX}/ai-content/generate",
        headers=auth_headers(token),
        json={"product_id": product["id"], "url": "https://example.com/other-product"},
    )
    assert invalid_response.status_code == 422


@pytest.mark.asyncio
async def test_queue_endpoints_and_publish(client, mock_queue_publish):
    _, token = await register_and_login(client, role="affiliate")
    headers = await workspace_auth_headers(token)

    create_resp = await client.post(
        f"{API_PREFIX}/queues",
        headers=headers,
        json={"content": "Publish me later"},
    )
    assert create_resp.status_code == 201
    item = create_resp.json()

    list_resp = await client.get(
        f"{API_PREFIX}/queues",
        headers=headers,
    )
    assert list_resp.status_code == 200
    assert any(entry["id"] == item["id"] for entry in list_resp.json()["items"])

    get_resp = await client.get(
        f"{API_PREFIX}/queues/{item['id']}",
        headers=headers,
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["content"] == "Publish me later"

    patch_resp = await client.patch(
        f"{API_PREFIX}/queues/{item['id']}",
        headers=headers,
        json={"title": "Updated Title"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["title"] == "Updated Title"

    publish_resp = await client.post(
        f"{API_PREFIX}/queues/{item['id']}/publish",
        headers=headers,
    )
    assert publish_resp.status_code == 200
    assert publish_resp.json()["telegram_message_id"] == 987654321

    delete_resp = await client.delete(
        f"{API_PREFIX}/queues/{item['id']}",
        headers=headers,
    )
    assert delete_resp.status_code == 200
    assert delete_resp.json()["message"] == "Queue item deleted successfully"


@pytest.mark.asyncio
async def test_aliexpress_import_endpoint_admin_only_and_validation(client, monkeypatch):
    _, admin_token = await register_and_login(client, role="admin")
    _, affiliate_token = await register_and_login(client, role="affiliate")

    async def fake_import_product(self, url=None, product_id=None):
        return AliExpressImportResponse(
            product={
                "id": str(uuid4()),
                "title": "AliExpress Product",
                "price": 10.0,
                "discount": 1.0,
                "rating": 4.0,
                "sales": 23,
                "reviews": 5,
                "image_url": "https://example.com/aliexpress.png",
                "product_url": "https://example.com/aliexpress",
                "score": 5.5,
                "status": "draft",
                "created_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
            },
            aliexpress_product_id="1234567890",
            imported=True,
            image_count=3,
        )

    monkeypatch.setattr(
        "app.services.aliexpress_import.AliExpressImportService.import_product",
        fake_import_product,
    )

    import_resp = await client.post(
        f"{API_PREFIX}/aliexpress/import",
        headers=auth_headers(admin_token),
        json={"url": "https://aliexpress.com/item/1234567890.html"},
    )
    assert import_resp.status_code == 201
    assert import_resp.json()["imported"] is True

    forbidden_resp = await client.post(
        f"{API_PREFIX}/aliexpress/import",
        headers=auth_headers(affiliate_token),
        json={"url": "https://aliexpress.com/item/1234567890.html"},
    )
    assert forbidden_resp.status_code == 403

    invalid_resp = await client.post(
        f"{API_PREFIX}/aliexpress/import",
        headers=auth_headers(admin_token),
        json={"url": "https://aliexpress.com/item/1234567890.html", "product_id": "123"},
    )
    assert invalid_resp.status_code == 422
