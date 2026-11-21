from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.enums import (
    BotPermissionStatus,
    FacebookPageValidationStatus,
)
from app.core.workspace import WORKSPACE_ID_HEADER
from app.models.automation_policy import AutomationPolicy
from app.models.channel import TelegramChannel
from app.models.facebook_page import FacebookPage
from tests.conftest import SessionLocal
from tests.test_api_endpoints import (
    API_PREFIX,
    add_workspace_member,
    auth_headers,
    register_and_login,
    workspace_auth_headers,
)

AUTOMATION = f"{API_PREFIX}/automation/config"


def _headers(token: str, workspace_id: str) -> dict[str, str]:
    headers = auth_headers(token)
    headers[WORKSPACE_ID_HEADER] = workspace_id
    return headers


async def _create_channel(workspace_id: str) -> UUID:
    async with SessionLocal() as session:
        channel = TelegramChannel(
            workspace_id=UUID(workspace_id),
            telegram_channel_id=f"test-{uuid4().hex}",
            title="Automation Test Channel",
            bot_permission_status=BotPermissionStatus.GRANTED,
            can_post_messages=True,
            can_edit_messages=True,
            can_delete_messages=True,
            is_active=True,
        )
        session.add(channel)
        await session.commit()
        await session.refresh(channel)
        return channel.id


async def _create_page(workspace_id: str, *, valid: bool = True) -> UUID:
    async with SessionLocal() as session:
        page = FacebookPage(
            workspace_id=UUID(workspace_id),
            facebook_page_id=f"page-{uuid4().hex}",
            page_name="Automation Test Page",
            encrypted_access_token="encrypted-test-value",
            validation_status=(
                FacebookPageValidationStatus.VALID
                if valid
                else FacebookPageValidationStatus.INVALID
            ),
            is_active=True,
        )
        session.add(page)
        await session.commit()
        await session.refresh(page)
        return page.id


async def _policy_for_workspace(workspace_id: str) -> AutomationPolicy | None:
    async with SessionLocal() as session:
        result = await session.execute(
            select(AutomationPolicy).where(
                AutomationPolicy.workspace_id == UUID(workspace_id)
            )
        )
        return result.scalar_one_or_none()


@pytest.mark.asyncio
async def test_get_returns_virtual_defaults_without_inserting_policy(client):
    _, token = await register_and_login(client, role="user")
    headers = await workspace_auth_headers(token)
    workspace_id = headers[WORKSPACE_ID_HEADER]

    response = await client.get(AUTOMATION, headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] is None
    assert body["workspace_id"] == workspace_id
    assert body["revision"] == 0
    assert body["enabled"] is False
    assert body["configuration_ready"] is False
    assert body["execution_available"] is False
    assert body["execution_state"] == "disabled"
    assert body["schedule"] == {
        "frequency": "daily",
        "preferred_time_local": "09:00",
        "timezone": "UTC",
        "posts_per_day": 1,
    }
    assert await _policy_for_workspace(workspace_id) is None


@pytest.mark.asyncio
async def test_first_patch_persists_filters_and_normalizes_keywords(client):
    _, token = await register_and_login(client, role="user")
    headers = await workspace_auth_headers(token)
    workspace_id = headers[WORKSPACE_ID_HEADER]
    channel_id = await _create_channel(workspace_id)

    response = await client.patch(
        AUTOMATION,
        headers=headers,
        json={
            "destination": {"provider": "telegram", "channel_id": str(channel_id)},
            "discovery": {
                "keywords": "  phone   case ",
                "min_price": "3.10",
                "max_price": "25.00",
                "min_commission": "4.50",
                "products_per_run": 12,
            },
            "schedule": {"preferred_time_local": "18:30", "posts_per_day": 2},
            "content": {"ai_provider": "gemini", "content_type": "telegram"},
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["revision"] == 1
    assert body["discovery"]["keywords"] == "phone case"
    assert body["discovery"]["min_price"] == "3.10"
    assert body["schedule"]["preferred_time_local"] == "18:30"
    assert body["content"]["ai_provider"] == "gemini"
    assert body["destination"]["status"] == "ready"
    assert body["execution_available"] is False
    assert body["execution_state"] == "disabled"


@pytest.mark.asyncio
async def test_enabled_policy_requires_eligible_destination(client):
    _, token = await register_and_login(client, role="user")
    headers = await workspace_auth_headers(token)

    missing_destination = await client.patch(
        AUTOMATION,
        headers=headers,
        json={"enabled": True},
    )
    assert missing_destination.status_code == 422

    page_id = await _create_page(headers[WORKSPACE_ID_HEADER], valid=False)
    invalid_page = await client.patch(
        AUTOMATION,
        headers=headers,
        json={
            "enabled": True,
            "destination": {"provider": "facebook", "page_id": str(page_id)},
        },
    )
    assert invalid_page.status_code == 422


@pytest.mark.asyncio
async def test_valid_enabled_policy_is_non_executable(client):
    _, token = await register_and_login(client, role="user")
    headers = await workspace_auth_headers(token)
    page_id = await _create_page(headers[WORKSPACE_ID_HEADER])

    response = await client.patch(
        AUTOMATION,
        headers=headers,
        json={
            "enabled": True,
            "destination": {"provider": "facebook", "page_id": str(page_id)},
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["enabled"] is True
    assert body["configuration_ready"] is True
    assert body["execution_available"] is False
    assert body["execution_state"] == "configured_ready_not_active"


@pytest.mark.asyncio
async def test_existing_policy_requires_matching_revision_and_increments_once(client):
    _, token = await register_and_login(client, role="user")
    headers = await workspace_auth_headers(token)

    created = await client.patch(
        AUTOMATION,
        headers=headers,
        json={"discovery": {"products_per_run": 7}},
    )
    assert created.status_code == 200
    assert created.json()["revision"] == 1

    missing_revision = await client.patch(
        AUTOMATION,
        headers=headers,
        json={"discovery": {"products_per_run": 8}},
    )
    assert missing_revision.status_code == 422

    stale = await client.patch(
        AUTOMATION,
        headers=headers,
        json={"expected_revision": 0, "discovery": {"products_per_run": 8}},
    )
    assert stale.status_code == 409

    updated = await client.patch(
        AUTOMATION,
        headers=headers,
        json={"expected_revision": 1, "discovery": {"products_per_run": 8}},
    )
    assert updated.status_code == 200
    assert updated.json()["revision"] == 2
    assert updated.json()["discovery"]["products_per_run"] == 8


@pytest.mark.asyncio
async def test_provider_switch_clears_previous_destination_atomically(client):
    _, token = await register_and_login(client, role="user")
    headers = await workspace_auth_headers(token)
    workspace_id = headers[WORKSPACE_ID_HEADER]
    channel_id = await _create_channel(workspace_id)
    page_id = await _create_page(workspace_id)

    first = await client.patch(
        AUTOMATION,
        headers=headers,
        json={"destination": {"provider": "telegram", "channel_id": str(channel_id)}},
    )
    assert first.status_code == 200

    second = await client.patch(
        AUTOMATION,
        headers=headers,
        json={
            "expected_revision": 1,
            "destination": {"provider": "facebook", "page_id": str(page_id)},
        },
    )
    assert second.status_code == 200
    assert second.json()["destination"]["provider"] == "facebook"
    assert second.json()["destination"]["page_id"] == str(page_id)
    policy = await _policy_for_workspace(workspace_id)
    assert policy is not None
    assert policy.telegram_channel_id is None
    assert policy.facebook_page_id == page_id


@pytest.mark.asyncio
async def test_members_can_read_but_cannot_patch(client):
    _, owner_token = await register_and_login(client, role="user")
    owner_headers = await workspace_auth_headers(owner_token)
    workspace_id = owner_headers[WORKSPACE_ID_HEADER]
    _, member_token = await register_and_login(client, role="user")
    await add_workspace_member(member_token, workspace_id)
    member_headers = _headers(member_token, workspace_id)

    readable = await client.get(AUTOMATION, headers=member_headers)
    assert readable.status_code == 200

    denied = await client.patch(
        AUTOMATION,
        headers=member_headers,
        json={"enabled": False},
    )
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_cross_workspace_access_is_rejected(client):
    _, token_a = await register_and_login(client, role="user")
    _, token_b = await register_and_login(client, role="user")
    headers_b = await workspace_auth_headers(token_b)

    response = await client.get(
        AUTOMATION,
        headers=_headers(token_a, headers_b[WORKSPACE_ID_HEADER]),
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_unknown_fields_and_invalid_ranges_are_rejected(client):
    _, token = await register_and_login(client, role="user")
    headers = await workspace_auth_headers(token)

    unknown = await client.patch(
        AUTOMATION,
        headers=headers,
        json={"execution_available": True},
    )
    assert unknown.status_code == 422

    invalid_range = await client.patch(
        AUTOMATION,
        headers=headers,
        json={
            "discovery": {
                "min_price": 20,
                "max_price": 10,
            }
        },
    )
    assert invalid_range.status_code == 422

    invalid_time = await client.patch(
        AUTOMATION,
        headers=headers,
        json={"schedule": {"preferred_time_local": "25:00"}},
    )
    assert invalid_time.status_code == 422


@pytest.mark.asyncio
async def test_invalid_destination_union_is_rejected(client):
    _, token = await register_and_login(client, role="user")
    headers = await workspace_auth_headers(token)

    response = await client.patch(
        AUTOMATION,
        headers=headers,
        json={
            "destination": {
                "provider": "telegram",
                "channel_id": str(uuid4()),
                "page_id": str(uuid4()),
            }
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_explicit_null_clears_nullable_fields(client):
    _, token = await register_and_login(client, role="user")
    headers = await workspace_auth_headers(token)
    created = await client.patch(
        AUTOMATION,
        headers=headers,
        json={
            "discovery": {"keywords": "wireless charger"},
            "content": {"ai_provider": "openai"},
        },
    )
    assert created.status_code == 200
    revision = created.json()["revision"]

    cleared = await client.patch(
        AUTOMATION,
        headers=headers,
        json={
            "expected_revision": revision,
            "destination": None,
            "discovery": {"keywords": None},
            "content": {"ai_provider": None},
        },
    )
    assert cleared.status_code == 200
    body = cleared.json()
    assert body["destination"] is None
    assert body["discovery"]["keywords"] is None
    assert body["content"]["ai_provider"] is None


@pytest.mark.asyncio
async def test_explicit_null_clears_facebook_destination(client):
    _, token = await register_and_login(client, role="user")
    headers = await workspace_auth_headers(token)
    page_id = await _create_page(headers[WORKSPACE_ID_HEADER])

    created = await client.patch(
        AUTOMATION,
        headers=headers,
        json={"destination": {"provider": "facebook", "page_id": str(page_id)}},
    )
    assert created.status_code == 200, created.text

    cleared = await client.patch(
        AUTOMATION,
        headers=headers,
        json={
            "expected_revision": created.json()["revision"],
            "destination": None,
        },
    )

    assert cleared.status_code == 200, cleared.text
    body = cleared.json()
    assert body["destination"] is None
    assert body["configuration_ready"] is False
    assert body["warnings"] == ["Select an active, validated Facebook Page"]
    policy = await _policy_for_workspace(headers[WORKSPACE_ID_HEADER])
    assert policy is not None
    assert policy.provider == "facebook"
    assert policy.telegram_channel_id is None
    assert policy.facebook_page_id is None


@pytest.mark.asyncio
async def test_database_constraints_protect_policy_ranges(session):
    from app.models.workspace import Workspace

    workspace = Workspace(name=f"constraint-{uuid4().hex}")
    session.add(workspace)
    await session.flush()
    session.add(
        AutomationPolicy(
            workspace_id=workspace.id,
            min_price=Decimal("20"),
            max_price=Decimal("10"),
        )
    )
    with pytest.raises(IntegrityError):
        await session.flush()
    await session.rollback()
