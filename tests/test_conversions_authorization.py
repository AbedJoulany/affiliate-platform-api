"""Phase D Task 4 — conversion authorization."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.rate_limit import limit_conversions
from app.core.workspace import WORKSPACE_ID_HEADER
from app.main import app as fastapi_app
from tests.test_api_endpoints import (
    API_PREFIX,
    activate_campaign,
    auth_headers,
    conversion_auth_headers,
    create_affiliate_profile,
    create_campaign,
    register_and_login,
    workspace_auth_headers,
)
from tests.test_rate_limit import _rate_limit_routes_on

PASSWORD = "StrongP@ssw0rd"


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


async def _enrolled_affiliate_and_campaign(client) -> tuple[str, dict, dict, dict]:
    _, token = await register_and_login(client, role="affiliate")
    _, admin_token = await register_and_login(client, role="admin")
    profile = await create_affiliate_profile(client, token)
    campaign = await create_campaign(client, admin_token)
    campaign = await activate_campaign(client, admin_token, campaign["id"])
    join = await client.post(
        f"{API_PREFIX}/affiliates/join-campaign",
        headers=auth_headers(token),
        json={"campaign_id": campaign["id"]},
    )
    assert join.status_code == 201
    headers = await conversion_auth_headers(token, campaign["id"])
    return token, profile, campaign, headers


@pytest.mark.asyncio
async def test_anonymous_conversion_is_rejected(client):
    response = await client.post(
        f"{API_PREFIX}/conversions",
        json=_conversion_body(str(uuid4()), str(uuid4())),
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


@pytest.mark.asyncio
async def test_invalid_access_token_cannot_create_conversion(client):
    response = await client.post(
        f"{API_PREFIX}/conversions",
        headers=auth_headers("not-a-valid-token"),
        json=_conversion_body(str(uuid4()), str(uuid4())),
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_owner_can_create_conversion_for_own_affiliate(client):
    token, profile, campaign, headers = await _enrolled_affiliate_and_campaign(client)
    response = await client.post(
        f"{API_PREFIX}/conversions",
        headers=headers,
        json=_conversion_body(profile["id"], campaign["id"]),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["affiliate_id"] == profile["id"]
    assert body["campaign_id"] == campaign["id"]
    assert body["status"] == "pending"
    assert Decimal(str(body["amount"])) == Decimal("125.50")
    assert Decimal(str(body["commission"])) == Decimal("12.55")
    assert body["currency"] == "USD"
    assert body["click_id"] == "click123"
    assert "id" in body


@pytest.mark.asyncio
async def test_user_cannot_create_conversion_for_another_affiliate(client):
    token_a, profile_a, campaign, headers_a = await _enrolled_affiliate_and_campaign(client)
    token_b, profile_b, _unused_campaign, _unused_headers = (
        await _enrolled_affiliate_and_campaign(client)
    )
    assert profile_a["id"] != profile_b["id"]

    join_b = await client.post(
        f"{API_PREFIX}/affiliates/join-campaign",
        headers=auth_headers(token_b),
        json={"campaign_id": campaign["id"]},
    )
    assert join_b.status_code == 201

    response = await client.post(
        f"{API_PREFIX}/conversions",
        headers=headers_a,
        json=_conversion_body(profile_b["id"], campaign["id"]),
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Insufficient permissions"}


@pytest.mark.asyncio
async def test_request_body_user_id_cannot_spoof_ownership(client):
    token_a, _, campaign, headers_a = await _enrolled_affiliate_and_campaign(client)
    token_b, profile_b, _unused_campaign, _unused_headers = (
        await _enrolled_affiliate_and_campaign(client)
    )
    me_b = await client.get(f"{API_PREFIX}/auth/me", headers=auth_headers(token_b))
    assert me_b.status_code == 200
    user_b_id = me_b.json()["id"]

    join_b = await client.post(
        f"{API_PREFIX}/affiliates/join-campaign",
        headers=auth_headers(token_b),
        json={"campaign_id": campaign["id"]},
    )
    assert join_b.status_code == 201

    response = await client.post(
        f"{API_PREFIX}/conversions",
        headers=headers_a,
        json=_conversion_body(
            profile_b["id"],
            campaign["id"],
            user_id=user_b_id,
            owner_id=user_b_id,
            affiliate_user_id=user_b_id,
        ),
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Insufficient permissions"}


@pytest.mark.asyncio
async def test_admin_can_create_conversion_for_another_users_affiliate(client):
    owner_token, profile, campaign, owner_headers = await _enrolled_affiliate_and_campaign(
        client
    )
    _, admin_token = await register_and_login(client, role="admin")
    me_owner = await client.get(f"{API_PREFIX}/auth/me", headers=auth_headers(owner_token))
    me_admin = await client.get(f"{API_PREFIX}/auth/me", headers=auth_headers(admin_token))
    assert me_owner.json()["id"] != me_admin.json()["id"]
    assert me_admin.json()["role"] == "admin"

    response = await client.post(
        f"{API_PREFIX}/conversions",
        headers={
            **auth_headers(admin_token),
            WORKSPACE_ID_HEADER: owner_headers[WORKSPACE_ID_HEADER],
        },
        json=_conversion_body(profile["id"], campaign["id"]),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["affiliate_id"] == profile["id"]
    assert body["status"] == "pending"
    assert Decimal(str(body["commission"])) == Decimal("12.55")


@pytest.mark.asyncio
async def test_admin_still_requires_authentication(client):
    response = await client.post(
        f"{API_PREFIX}/conversions",
        json=_conversion_body(str(uuid4()), str(uuid4())),
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_does_not_bypass_conversion_validation(client):
    _, admin_token = await register_and_login(client, role="admin")
    response = await client.post(
        f"{API_PREFIX}/conversions",
        headers=await workspace_auth_headers(admin_token),
        json={"amount": 1},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_missing_affiliate_returns_not_found(client):
    token, _, campaign, headers = await _enrolled_affiliate_and_campaign(client)
    missing_id = str(uuid4())
    response = await client.post(
        f"{API_PREFIX}/conversions",
        headers=headers,
        json=_conversion_body(missing_id, campaign["id"]),
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Affiliate not found"}
    assert missing_id not in str(response.json())


@pytest.mark.asyncio
async def test_cross_user_forbidden_does_not_leak_affiliate_payload(client):
    token_a, _, campaign, headers_a = await _enrolled_affiliate_and_campaign(client)
    token_b, profile_b, _unused_campaign, _unused_headers = (
        await _enrolled_affiliate_and_campaign(client)
    )
    join_b = await client.post(
        f"{API_PREFIX}/affiliates/join-campaign",
        headers=auth_headers(token_b),
        json={"campaign_id": campaign["id"]},
    )
    assert join_b.status_code == 201

    response = await client.post(
        f"{API_PREFIX}/conversions",
        headers=headers_a,
        json=_conversion_body(profile_b["id"], campaign["id"]),
    )
    assert response.status_code == 403
    detail = str(response.json())
    assert profile_b["id"] not in detail
    assert "user_id" not in detail


@pytest.mark.asyncio
async def test_conversion_rate_limit_dependency_remains(client):
    assert _rate_limit_routes_on(f"{API_PREFIX}/conversions", "POST") == {"conversions"}
    assert limit_conversions.__rate_limit_route__ == "conversions"


def test_public_and_sse_routes_unchanged():
    assert _rate_limit_routes_on("/health", "GET") == set()
    assert _rate_limit_routes_on("/ready", "GET") == set()
    assert _rate_limit_routes_on("/worker/health", "GET") == set()
    assert _rate_limit_routes_on(f"{API_PREFIX}/queues/stream", "GET") == set()

    from fastapi.routing import APIRoute

    def walk(router, prefix: str = ""):
        for route in router.routes:
            if isinstance(route, APIRoute):
                yield prefix + route.path, route
            elif type(route).__name__ == "_IncludedRouter":
                nested = prefix + (route.include_context.prefix or "")
                yield from walk(route.original_router, nested)

    stream = next(
        route
        for path, route in walk(fastapi_app.router)
        if path == f"{API_PREFIX}/queues/stream"
    )
    calls = []

    def collect(dependant):
        for dep in dependant.dependencies:
            if dep.call is not None:
                calls.append(dep.call)
            collect(dep)

    collect(stream.dependant)
    assert limit_conversions not in calls
