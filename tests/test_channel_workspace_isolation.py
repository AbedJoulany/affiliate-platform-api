"""Phase E Task 6 — Telegram channel workspace isolation."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.auth.security import decode_access_token
from app.core.enums import WorkspaceMembershipRole
from app.core.workspace import WORKSPACE_ID_HEADER
from app.models.channel import TelegramChannel
from app.models.workspace import Workspace, WorkspaceMembership
from tests.conftest import SessionLocal
from tests.test_api_endpoints import API_PREFIX, auth_headers, register_and_login

CHANNELS = f"{API_PREFIX}/channels"


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


def _channel_payload(suffix: str | None = None, **extra) -> dict:
    tag = suffix or uuid4().hex[:10]
    body = {
        "telegram_channel_id": f"@channel{tag}",
        "title": f"Channel {tag}",
    }
    body.update(extra)
    return body


async def _create_channel(client, token: str, workspace_id: str, **payload) -> dict:
    response = await client.post(
        CHANNELS,
        headers=_headers(token, workspace_id),
        json=_channel_payload(**payload),
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_unauthenticated_channel_request_is_401(client):
    response = await client.get(CHANNELS)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_missing_workspace_header_is_rejected(client):
    _, token = await register_and_login(client, role="user")
    response = await client.get(CHANNELS, headers=auth_headers(token))
    assert response.status_code == 403
    assert response.json() == {"detail": "Insufficient permissions"}


@pytest.mark.asyncio
async def test_malformed_workspace_header_is_rejected(client):
    _, token = await register_and_login(client, role="user")
    response = await client.get(CHANNELS, headers=_headers(token, "not-a-uuid"))
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_unknown_workspace_is_rejected(client):
    _, token = await register_and_login(client, role="user")
    response = await client.get(CHANNELS, headers=_headers(token, str(uuid4())))
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_non_member_workspace_is_rejected(client):
    _, owner_token = await register_and_login(client, role="user")
    _, stranger_token = await register_and_login(client, role="user")
    workspace_id = await _create_workspace_for_user(owner_token, name="Private")
    response = await client.get(CHANNELS, headers=_headers(stranger_token, workspace_id))
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_member_lists_only_own_workspace_channels(
    client,
    mock_telegram_permissions,
):
    _, token = await register_and_login(client, role="user")
    workspace_a = await _create_workspace_for_user(token, name="Channels A")
    workspace_b = await _create_workspace_for_user(token, name="Channels B")
    channel_a = await _create_channel(client, token, workspace_a, suffix="a1")
    channel_b = await _create_channel(client, token, workspace_b, suffix="b1")

    listed_a = await client.get(CHANNELS, headers=_headers(token, workspace_a))
    listed_b = await client.get(CHANNELS, headers=_headers(token, workspace_b))
    assert listed_a.status_code == 200
    assert listed_b.status_code == 200
    ids_a = {item["id"] for item in listed_a.json()["items"]}
    ids_b = {item["id"] for item in listed_b.json()["items"]}
    assert channel_a["id"] in ids_a
    assert channel_b["id"] not in ids_a
    assert channel_b["id"] in ids_b
    assert channel_a["id"] not in ids_b


@pytest.mark.asyncio
async def test_cross_workspace_update_and_delete_are_404(
    client,
    mock_telegram_permissions,
):
    _, token_a = await register_and_login(client, role="user")
    _, token_b = await register_and_login(client, role="user")
    workspace_a = await _create_workspace_for_user(token_a, name="A")
    workspace_b = await _create_workspace_for_user(token_b, name="B")
    channel_a = await _create_channel(client, token_a, workspace_a, suffix="xa")

    updated = await client.put(
        f"{CHANNELS}/{channel_a['id']}",
        headers=_headers(token_b, workspace_b),
        json={"title": "Hijack"},
    )
    assert updated.status_code == 404
    assert updated.json() == {"detail": "Channel not found"}

    deleted = await client.delete(
        f"{CHANNELS}/{channel_a['id']}",
        headers=_headers(token_b, workspace_b),
    )
    assert deleted.status_code == 404
    assert deleted.json() == {"detail": "Channel not found"}


@pytest.mark.asyncio
async def test_create_assigns_workspace_from_header_not_body(
    client,
    mock_telegram_permissions,
):
    _, token = await register_and_login(client, role="user")
    workspace_a = await _create_workspace_for_user(token, name="Header A")
    workspace_b = await _create_workspace_for_user(token, name="Header B")
    payload = _channel_payload(suffix="hdr")
    payload["workspace_id"] = workspace_b

    created = await client.post(
        CHANNELS,
        headers=_headers(token, workspace_a),
        json=payload,
    )
    assert created.status_code == 201
    channel_id = UUID(created.json()["id"])

    async with SessionLocal() as session:
        channel = await session.get(TelegramChannel, channel_id)
        assert channel is not None
        assert str(channel.workspace_id) == workspace_a

    listed_b = await client.get(CHANNELS, headers=_headers(token, workspace_b))
    assert created.json()["id"] not in {item["id"] for item in listed_b.json()["items"]}


@pytest.mark.asyncio
async def test_duplicate_telegram_channel_id_is_globally_rejected(
    client,
    mock_telegram_permissions,
):
    _, token_a = await register_and_login(client, role="user")
    _, token_b = await register_and_login(client, role="user")
    workspace_a = await _create_workspace_for_user(token_a, name="Unique A")
    workspace_b = await _create_workspace_for_user(token_b, name="Unique B")
    await _create_channel(client, token_a, workspace_a, suffix="dup")

    duplicate = await client.post(
        CHANNELS,
        headers=_headers(token_b, workspace_b),
        json=_channel_payload(suffix="dup"),
    )
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "Telegram channel already registered"}


@pytest.mark.asyncio
async def test_admin_can_operate_without_membership(
    client,
    mock_telegram_permissions,
):
    _, owner_token = await register_and_login(client, role="user")
    _, admin_token = await register_and_login(client, role="admin")
    workspace = await _create_workspace_for_user(owner_token, name="Admin target")
    channel = await _create_channel(client, owner_token, workspace, suffix="adm")

    listed = await client.get(CHANNELS, headers=_headers(admin_token, workspace))
    assert listed.status_code == 200
    assert channel["id"] in {item["id"] for item in listed.json()["items"]}

    updated = await client.put(
        f"{CHANNELS}/{channel['id']}",
        headers=_headers(admin_token, workspace),
        json={"title": "Admin title"},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Admin title"


@pytest.mark.asyncio
async def test_admin_requires_workspace_header_and_stays_scoped(
    client,
    mock_telegram_permissions,
):
    _, token_a = await register_and_login(client, role="user")
    _, token_b = await register_and_login(client, role="user")
    _, admin_token = await register_and_login(client, role="admin")
    workspace_a = await _create_workspace_for_user(token_a, name="Admin A")
    workspace_b = await _create_workspace_for_user(token_b, name="Admin B")
    channel_b = await _create_channel(client, token_b, workspace_b, suffix="adb")

    missing = await client.get(CHANNELS, headers=auth_headers(admin_token))
    assert missing.status_code == 403

    leaked = await client.put(
        f"{CHANNELS}/{channel_b['id']}",
        headers=_headers(admin_token, workspace_a),
        json={"title": "cross"},
    )
    assert leaked.status_code == 404
