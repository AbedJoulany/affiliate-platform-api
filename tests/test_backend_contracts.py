from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete

from app.core.enums import ProductStatus, QueueStatus
from app.core.workspace import WORKSPACE_ID_HEADER
from app.models.aliexpress_category import AliExpressCategory
from app.models.channel import TelegramChannel
from app.models.product import Product
from app.models.queue import QueueItem
from app.services.health import ReadinessService
from tests.test_api_endpoints import workspace_auth_headers

API_PREFIX = "/api/v1"
PASSWORD = "StrongP@ssw0rd"


async def authenticated_headers(client) -> dict[str, str]:
    email = f"contracts-{uuid4().hex[:8]}@example.com"
    response = await client.post(
        f"{API_PREFIX}/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "full_name": "Contract Tester",
        },
    )
    assert response.status_code == 201
    response = await client.post(
        f"{API_PREFIX}/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.mark.asyncio
async def test_cached_aliexpress_categories_are_authenticated(client, session):
    await session.execute(delete(AliExpressCategory))
    synced_at = datetime.now(UTC)
    session.add_all(
        [
            AliExpressCategory(
                category_id=1,
                category_name="Apparel",
                parent_category_id=0,
                synced_at=synced_at,
            ),
            AliExpressCategory(
                category_id=2,
                category_name="Shoes",
                parent_category_id=1,
                synced_at=synced_at,
            ),
        ]
    )
    await session.commit()

    unauthenticated = await client.get(f"{API_PREFIX}/aliexpress/categories")
    assert unauthenticated.status_code == 401

    response = await client.get(
        f"{API_PREFIX}/aliexpress/categories",
        headers=await authenticated_headers(client),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [item["category_id"] for item in body["items"]] == [1, 2]
    assert body["synced_at"] is not None

    await session.execute(delete(AliExpressCategory))
    await session.commit()


@pytest.mark.asyncio
async def test_dashboard_returns_canonical_aggregates(client, session):
    await session.execute(delete(QueueItem))
    await session.execute(delete(Product))
    await session.execute(delete(TelegramChannel))

    auth = await authenticated_headers(client)
    token = auth["Authorization"].removeprefix("Bearer ")
    headers = await workspace_auth_headers(token)
    workspace_id = UUID(headers[WORKSPACE_ID_HEADER])

    products = [
        Product(
            title="Active product",
            price=Decimal("10.00"),
            image_url="https://example.com/active.png",
            product_url="https://example.com/active",
            status=ProductStatus.ACTIVE,
        ),
        Product(
            title="Draft product",
            price=Decimal("20.00"),
            image_url="https://example.com/draft.png",
            product_url="https://example.com/draft",
            status=ProductStatus.DRAFT,
        ),
    ]
    channels = [
        TelegramChannel(
            telegram_channel_id="@active",
            title="Active",
            is_active=True,
            workspace_id=workspace_id,
        ),
        TelegramChannel(
            telegram_channel_id="@inactive",
            title="Inactive",
            is_active=False,
            workspace_id=workspace_id,
        ),
    ]
    session.add_all([*products, *channels])
    await session.flush()
    session.add_all(
        [
            QueueItem(
                title=f"{status.value} item",
                content="content",
                status=status,
                workspace_id=workspace_id,
            )
            for status in QueueStatus
        ]
    )
    await session.commit()

    unauthenticated = await client.get(f"{API_PREFIX}/dashboard")
    assert unauthenticated.status_code == 401

    response = await client.get(
        f"{API_PREFIX}/dashboard",
        params={"activity_limit": 3},
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["products"] == {
        "total": 2,
        "by_status": {"draft": 1, "active": 1, "inactive": 0, "archived": 0},
    }
    assert body["queue"] == {
        "total": 4,
        "by_status": {"draft": 1, "queued": 1, "scheduled": 1, "published": 1},
    }
    assert body["channels"] == {"total": 2, "active": 1, "inactive": 1}
    assert len(body["recent_activity"]) == 3
    assert {item["resource_type"] for item in body["recent_activity"]} <= {
        "product",
        "queue",
    }
    assert body["system_status"]["status"] == "operational"
    assert body["system_status"]["database"] == "up"

    await session.execute(delete(QueueItem))
    await session.execute(delete(Product))
    await session.execute(delete(TelegramChannel))
    await session.commit()


@pytest.mark.asyncio
async def test_readiness_reports_dependencies_separately(client, monkeypatch):
    async def redis_is_up(self) -> bool:
        return True

    monkeypatch.setattr(ReadinessService, "_check_redis", redis_is_up)
    response = await client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {
            "database": {"status": "up"},
            "redis": {"status": "up"},
        },
    }


@pytest.mark.asyncio
async def test_readiness_is_sanitized_when_a_dependency_is_down(client, monkeypatch):
    async def database_is_up(self) -> bool:
        return True

    async def redis_is_down(self) -> bool:
        return False

    monkeypatch.setattr(ReadinessService, "_check_database", database_is_up)
    monkeypatch.setattr(ReadinessService, "_check_redis", redis_is_down)
    response = await client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {
            "database": {"status": "up"},
            "redis": {"status": "down"},
        },
    }
