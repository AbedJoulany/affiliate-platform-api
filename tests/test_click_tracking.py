"""Phase E Task 11 — public click tracking and Conversion.click_id producer."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.core.rate_limit import CLICK_LIMIT, CLICK_WINDOW_SECONDS, limit_clicks
from app.models.affiliate import AffiliateCampaign
from app.models.click import Click
from app.models.conversion import Conversion
from tests.conftest import SessionLocal
from tests.test_api_endpoints import (
    API_PREFIX,
    activate_campaign,
    conversion_auth_headers,
    create_affiliate_profile,
    create_campaign,
    join_campaign,
    register_and_login,
)
from tests.test_rate_limit import FakeRedis, _rate_limit_routes_on

CONVERSION_CLICK_ID_MAX_LENGTH = 64


async def _enrolled_tracking_link(client) -> tuple[str, dict, dict, dict]:
    _, affiliate_token = await register_and_login(client, role="affiliate")
    _, admin_token = await register_and_login(client, role="admin")
    profile = await create_affiliate_profile(client, affiliate_token)
    campaign = await create_campaign(client, admin_token)
    campaign = await activate_campaign(client, admin_token, campaign["id"])
    join = await join_campaign(client, affiliate_token, campaign["id"])
    assert join.status_code == 201
    return affiliate_token, profile, campaign, join.json()


async def _click_count() -> int:
    async with SessionLocal() as session:
        result = await session.execute(select(func.count()).select_from(Click))
        return int(result.scalar_one())


async def _clicks_for_link(affiliate_campaign_id: str) -> list[Click]:
    async with SessionLocal() as session:
        result = await session.execute(
            select(Click).where(Click.affiliate_campaign_id == UUID(affiliate_campaign_id))
        )
        return list(result.scalars().all())


async def _set_tracking_link(affiliate_campaign_id: str, tracking_link: str) -> None:
    async with SessionLocal() as session:
        link = await session.get(AffiliateCampaign, UUID(affiliate_campaign_id))
        assert link is not None
        link.tracking_link = tracking_link
        await session.commit()


@pytest.fixture
def fake_redis(monkeypatch) -> FakeRedis:
    store = FakeRedis()

    async def _get_fake():
        return store

    monkeypatch.setattr("app.core.rate_limit.get_rate_limit_redis", _get_fake)
    return store


@pytest.mark.asyncio
async def test_successful_click_persists_and_redirects(client):
    _, _profile, _campaign, link = await _enrolled_tracking_link(client)
    before = await _click_count()

    response = await client.get(
        f"{API_PREFIX}/clicks/{link['id']}",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == link["tracking_link"]

    clicks = await _clicks_for_link(link["id"])
    assert len(clicks) == 1
    assert await _click_count() == before + 1
    click = clicks[0]
    assert str(click.affiliate_campaign_id) == link["id"]
    assert click.click_id
    assert len(click.click_id) <= CONVERSION_CLICK_ID_MAX_LENGTH
    assert click.click_id.isascii()
    assert "/" not in click.click_id
    assert "?" not in click.click_id


@pytest.mark.asyncio
async def test_generated_click_ids_are_unique(client):
    _, _profile, _campaign, link = await _enrolled_tracking_link(client)

    first = await client.get(f"{API_PREFIX}/clicks/{link['id']}", follow_redirects=False)
    second = await client.get(f"{API_PREFIX}/clicks/{link['id']}", follow_redirects=False)
    assert first.status_code == 302
    assert second.status_code == 302

    clicks = await _clicks_for_link(link["id"])
    click_ids = [row.click_id for row in clicks]
    assert len(click_ids) == 2
    assert len(set(click_ids)) == 2


@pytest.mark.asyncio
async def test_missing_campaign_returns_404_and_does_not_persist(client):
    before = await _click_count()
    missing_id = uuid4()

    response = await client.get(
        f"{API_PREFIX}/clicks/{missing_id}",
        follow_redirects=False,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Affiliate campaign not found"
    assert await _click_count() == before


@pytest.mark.asyncio
async def test_missing_tracking_link_returns_422_and_does_not_persist(client):
    _, _profile, _campaign, link = await _enrolled_tracking_link(client)
    await _set_tracking_link(link["id"], "")
    before = await _click_count()

    response = await client.get(
        f"{API_PREFIX}/clicks/{link['id']}",
        follow_redirects=False,
    )

    assert response.status_code == 422
    assert "tracking link" in response.json()["detail"].lower()
    assert await _click_count() == before


@pytest.mark.asyncio
async def test_click_endpoint_eventually_rate_limits(client, fake_redis):
    missing_id = uuid4()
    path = f"{API_PREFIX}/clicks/{missing_id}"
    before = await _click_count()

    for _ in range(CLICK_LIMIT):
        response = await client.get(path, follow_redirects=False)
        assert response.status_code == 404

    blocked = await client.get(path, follow_redirects=False)
    assert blocked.status_code == 429
    assert blocked.json() == {"detail": "Rate limit exceeded"}
    retry_after = blocked.headers.get("retry-after")
    assert retry_after is not None
    assert retry_after.isdigit()
    assert any(key.startswith("ratelimit:clicks:ip:") for key in fake_redis.counts)
    assert fake_redis.expire_calls
    assert fake_redis.expire_calls[0][1] == CLICK_WINDOW_SECONDS
    assert await _click_count() == before


@pytest.mark.asyncio
async def test_conversion_can_correlate_to_generated_click_id(client):
    token, profile, campaign, link = await _enrolled_tracking_link(client)
    redirect = await client.get(f"{API_PREFIX}/clicks/{link['id']}", follow_redirects=False)
    assert redirect.status_code == 302
    click = (await _clicks_for_link(link["id"]))[0]

    headers = await conversion_auth_headers(token, campaign["id"])
    response = await client.post(
        f"{API_PREFIX}/conversions",
        headers=headers,
        json={
            "affiliate_id": profile["id"],
            "campaign_id": campaign["id"],
            "external_order_id": f"order-{uuid4().hex[:8]}",
            "amount": 50.0,
            "currency": "USD",
            "click_id": click.click_id,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["click_id"] == click.click_id

    async with SessionLocal() as session:
        stored = await session.get(Conversion, UUID(body["id"]))
        assert stored is not None
        assert stored.click_id == click.click_id


@pytest.mark.asyncio
async def test_conversion_without_click_id_still_succeeds(client):
    token, profile, campaign, _link = await _enrolled_tracking_link(client)
    headers = await conversion_auth_headers(token, campaign["id"])

    response = await client.post(
        f"{API_PREFIX}/conversions",
        headers=headers,
        json={
            "affiliate_id": profile["id"],
            "campaign_id": campaign["id"],
            "external_order_id": f"order-{uuid4().hex[:8]}",
            "amount": 50.0,
            "currency": "USD",
        },
    )
    assert response.status_code == 201
    assert response.json()["click_id"] is None


@pytest.mark.asyncio
async def test_click_endpoint_is_public(client):
    _, _profile, _campaign, link = await _enrolled_tracking_link(client)

    response = await client.get(
        f"{API_PREFIX}/clicks/{link['id']}",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert "www-authenticate" not in {key.lower() for key in response.headers}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "unsafe_url",
    [
        "javascript:alert(1)",
        "/relative/path",
        "ftp://example.com/landing",
        "https://",
        "data:text/html,hi",
        "http://example.com\nLocation: https://evil.test",
    ],
)
async def test_unsafe_tracking_link_is_rejected(client, unsafe_url: str):
    _, _profile, _campaign, link = await _enrolled_tracking_link(client)
    await _set_tracking_link(link["id"], unsafe_url)
    before = await _click_count()

    response = await client.get(
        f"{API_PREFIX}/clicks/{link['id']}",
        follow_redirects=False,
    )

    assert response.status_code == 422
    assert await _click_count() == before
    assert "location" not in {key.lower() for key in response.headers}


def test_click_route_uses_existing_rate_limit_primitive():
    assert _rate_limit_routes_on(f"{API_PREFIX}/clicks/{{affiliate_campaign_id}}", "GET") == {
        "clicks"
    }
    assert limit_clicks.__rate_limit_route__ == "clicks"
