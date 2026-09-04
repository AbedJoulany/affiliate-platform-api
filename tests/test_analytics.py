"""Phase E Tasks 12–13 — workspace-scoped analytics aggregates."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.core.workspace import WORKSPACE_ID_HEADER
from app.models.click import Click, generate_click_id
from app.models.conversion import Conversion
from app.services.analytics import conversion_rate, resolve_analytics_window
from app.services.exceptions import ValidationError
from tests.conftest import SessionLocal
from tests.test_api_endpoints import (
    API_PREFIX,
    activate_campaign,
    auth_headers,
    create_affiliate_profile,
    create_campaign,
    join_campaign,
    register_and_login,
    workspace_auth_headers,
)
from tests.test_campaign_workspace_isolation import _create_workspace_for_user

ANALYTICS = f"{API_PREFIX}/analytics"
DAY_A = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)
DAY_B = datetime(2026, 8, 11, 15, 30, tzinfo=UTC)


def test_conversion_rate_is_zero_when_clicks_are_zero():
    assert conversion_rate(0, 0) == 0.0
    assert conversion_rate(0, 9) == 0.0
    assert conversion_rate(4, 1) == 0.25


def test_resolve_analytics_window_rejects_inverted_and_overlong_ranges():
    now = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
    start, end = resolve_analytics_window(None, None, now=now)
    assert end == now
    assert start == now - timedelta(days=30)

    with pytest.raises(ValidationError, match="Invalid date range"):
        resolve_analytics_window(now, now - timedelta(days=1), now=now)

    with pytest.raises(ValidationError, match="1 year"):
        resolve_analytics_window(now - timedelta(days=367), now, now=now)


async def _insert_click(link_id: str, when: datetime, click_id: str | None = None) -> str:
    token = click_id or generate_click_id()
    async with SessionLocal() as session:
        session.add(
            Click(
                affiliate_campaign_id=UUID(link_id),
                click_id=token,
                created_at=when,
                updated_at=when,
            )
        )
        await session.commit()
    return token


async def _insert_conversion(
    *,
    affiliate_id: str,
    campaign_id: str,
    when: datetime,
    amount: str = "50.00",
    click_id: str | None = None,
) -> None:
    async with SessionLocal() as session:
        session.add(
            Conversion(
                affiliate_id=UUID(affiliate_id),
                campaign_id=UUID(campaign_id),
                external_order_id=f"analytics-{uuid4().hex[:12]}",
                amount=Decimal(amount),
                commission=Decimal("5.00"),
                currency="USD",
                click_id=click_id,
                created_at=when,
                updated_at=when,
            )
        )
        await session.commit()


async def _enroll(client) -> tuple[str, dict, dict, dict, dict[str, str]]:
    _, affiliate_token = await register_and_login(client, role="affiliate")
    _, admin_token = await register_and_login(client, role="admin")
    profile = await create_affiliate_profile(client, affiliate_token)
    campaign = await create_campaign(client, admin_token)
    campaign = await activate_campaign(client, admin_token, campaign["id"])
    headers = await workspace_auth_headers(admin_token)
    join = await join_campaign(client, affiliate_token, campaign["id"])
    assert join.status_code == 201
    return admin_token, profile, campaign, join.json(), headers


@pytest.mark.asyncio
async def test_overview_requires_auth_and_workspace(client):
    unauthenticated = await client.get(f"{ANALYTICS}/overview")
    assert unauthenticated.status_code == 401

    _, token = await register_and_login(client, role="advertiser")
    missing_workspace = await client.get(
        f"{ANALYTICS}/overview",
        headers=auth_headers(token),
    )
    assert missing_workspace.status_code == 403


@pytest.mark.asyncio
async def test_overview_empty_shape(client):
    token, _profile, _campaign, _link, headers = await _enroll(client)
    response = await client.get(
        f"{ANALYTICS}/overview",
        headers=headers,
        params={"from": "2026-08-01T00:00:00Z", "to": "2026-08-31T23:59:59Z"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_clicks"] == 0
    assert body["total_conversions"] == 0
    assert body["conversion_rate"] == 0
    assert Decimal(str(body["total_revenue"])) == Decimal("0.00")
    assert "from" in body and "to" in body
    assert isinstance(body["by_day"], list)
    assert body["by_day"]
    assert all(point["clicks"] == 0 and point["conversions"] == 0 for point in body["by_day"])
    assert token  # enrollment succeeded with an admin token


@pytest.mark.asyncio
async def test_overview_aggregates_seeded_workspace_data(client):
    _token, profile, campaign, link, headers = await _enroll(client)
    click_a = await _insert_click(link["id"], DAY_A)
    await _insert_click(link["id"], DAY_A)
    await _insert_click(link["id"], DAY_B)
    await _insert_conversion(
        affiliate_id=profile["id"],
        campaign_id=campaign["id"],
        when=DAY_A,
        amount="40.00",
        click_id=click_a,
    )
    await _insert_conversion(
        affiliate_id=profile["id"],
        campaign_id=campaign["id"],
        when=DAY_B,
        amount="10.00",
    )

    response = await client.get(
        f"{ANALYTICS}/overview",
        headers=headers,
        params={"from": "2026-08-10T00:00:00Z", "to": "2026-08-11T23:59:59Z"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_clicks"] == 3
    assert body["total_conversions"] == 2
    assert body["conversion_rate"] == 0.6667
    assert Decimal(str(body["total_revenue"])) == Decimal("50.00")
    by_day = {point["date"]: point for point in body["by_day"]}
    assert by_day["2026-08-10"]["clicks"] == 2
    assert by_day["2026-08-10"]["conversions"] == 1
    assert by_day["2026-08-11"]["clicks"] == 1
    assert by_day["2026-08-11"]["conversions"] == 1


@pytest.mark.asyncio
async def test_overview_excludes_other_workspace_campaigns(client):
    token_a, profile_a, campaign_a, link_a, headers_a = await _enroll(client)
    token_b, profile_b, campaign_b, link_b, _headers_b = await _enroll(client)
    await _insert_click(link_a["id"], DAY_A)
    await _insert_click(link_b["id"], DAY_A)
    await _insert_click(link_b["id"], DAY_A)
    await _insert_conversion(
        affiliate_id=profile_b["id"],
        campaign_id=campaign_b["id"],
        when=DAY_A,
        amount="99.00",
    )

    response = await client.get(
        f"{ANALYTICS}/overview",
        headers=headers_a,
        params={"from": "2026-08-10T00:00:00Z", "to": "2026-08-10T23:59:59Z"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_clicks"] == 1
    assert body["total_conversions"] == 0
    assert Decimal(str(body["total_revenue"])) == Decimal("0.00")
    assert token_a and token_b and profile_a and campaign_a


@pytest.mark.asyncio
async def test_date_range_validation(client):
    _token, _profile, _campaign, _link, headers = await _enroll(client)

    inverted = await client.get(
        f"{ANALYTICS}/overview",
        headers=headers,
        params={"from": "2026-08-20T00:00:00Z", "to": "2026-08-10T00:00:00Z"},
    )
    assert inverted.status_code == 422

    too_long = await client.get(
        f"{ANALYTICS}/overview",
        headers=headers,
        params={"from": "2025-01-01T00:00:00Z", "to": "2026-09-04T00:00:00Z"},
    )
    assert too_long.status_code == 422


@pytest.mark.asyncio
async def test_campaign_funnel_404_for_cross_workspace_id(client):
    _token_a, _profile_a, _campaign_a, _link_a, headers_a = await _enroll(client)
    _token_b, _profile_b, campaign_b, _link_b, _headers_b = await _enroll(client)

    missing = await client.get(
        f"{ANALYTICS}/campaigns/{uuid4()}/funnel",
        headers=headers_a,
    )
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Campaign not found"}

    cross = await client.get(
        f"{ANALYTICS}/campaigns/{campaign_b['id']}/funnel",
        headers=headers_a,
    )
    assert cross.status_code == 404
    assert cross.json() == {"detail": "Campaign not found"}


@pytest.mark.asyncio
async def test_campaign_funnel_correlates_clicks_and_conversions(client):
    _token, profile, campaign, link, headers = await _enroll(client)
    matched = await _insert_click(link["id"], DAY_A)
    await _insert_click(link["id"], DAY_A)
    await _insert_conversion(
        affiliate_id=profile["id"],
        campaign_id=campaign["id"],
        when=DAY_A,
        amount="25.00",
        click_id=matched,
    )
    await _insert_conversion(
        affiliate_id=profile["id"],
        campaign_id=campaign["id"],
        when=DAY_A,
        amount="15.00",
    )

    response = await client.get(
        f"{ANALYTICS}/campaigns/{campaign['id']}/funnel",
        headers=headers,
        params={"from": "2026-08-10T00:00:00Z", "to": "2026-08-10T23:59:59Z"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["campaign_id"] == campaign["id"]
    assert body["campaign_name"] == campaign["name"]
    assert body["total_clicks"] == 2
    assert body["total_conversions"] == 2
    assert body["attributed_conversions"] == 1
    assert body["conversion_rate"] == 1.0
    assert Decimal(str(body["total_revenue"])) == Decimal("40.00")


@pytest.mark.asyncio
async def test_analytics_admin_can_name_workspace_without_membership(client):
    _, admin_token = await register_and_login(client, role="admin")
    _, member_token = await register_and_login(client, role="advertiser")
    workspace_id = await _create_workspace_for_user(member_token, name="Analytics Admin WS")
    headers = {
        **auth_headers(admin_token),
        WORKSPACE_ID_HEADER: workspace_id,
    }
    response = await client.get(f"{ANALYTICS}/overview", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["total_clicks"] == 0
