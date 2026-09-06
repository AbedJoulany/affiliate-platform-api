from datetime import UTC, datetime
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
    """Bearer token plus a live workspace membership for tenant isolation."""
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


@pytest.mark.asyncio
async def test_public_registration_always_creates_user_and_rejects_role(client):
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
    assert response.json()["role"] == "user"

    for role in ("admin", "advertiser", "affiliate"):
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


async def register_and_login(client, role: str = "user") -> tuple[str, str]:
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


@pytest.mark.asyncio
async def test_auth_register_login_and_profile_endpoints(client):
    _, token = await register_and_login(client, role="user")

    response = await client.get(f"{API_PREFIX}/auth/me", headers=auth_headers(token))
    assert response.status_code == 200
    body = response.json()
    assert body["email"].endswith("@example.com")
    assert body["role"] == "user"
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
async def test_product_crud_and_search_filters(client):
    _, admin_token = await register_and_login(client, role="admin")
    _, user_token = await register_and_login(client, role="user")

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
        headers=auth_headers(user_token),
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
    _, token = await register_and_login(client, role="user")
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
    _, token = await register_and_login(client, role="user")

    _admin_email, admin_token = await register_and_login(client, role="admin")
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
    _, token = await register_and_login(client, role="user")
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
    _, user_token = await register_and_login(client, role="user")

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
        headers=auth_headers(user_token),
        json={"url": "https://aliexpress.com/item/1234567890.html"},
    )
    assert forbidden_resp.status_code == 403

    invalid_resp = await client.post(
        f"{API_PREFIX}/aliexpress/import",
        headers=auth_headers(admin_token),
        json={"url": "https://aliexpress.com/item/1234567890.html", "product_id": "123"},
    )
    assert invalid_resp.status_code == 422
