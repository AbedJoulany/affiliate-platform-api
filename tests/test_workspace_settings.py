"""Phase E Task 14 — workspace settings + self-service profile PATCH."""

from __future__ import annotations

import json
from uuid import uuid4

import pytest

from app.core.config import get_settings
from app.core.enums import UserRole
from app.core.workspace import WORKSPACE_ID_HEADER
from tests.test_api_endpoints import (
    API_PREFIX,
    add_workspace_member,
    auth_headers,
    register_and_login,
    workspace_auth_headers,
)
from tests.test_campaign_workspace_isolation import _create_workspace_for_user

SETTINGS = f"{API_PREFIX}/workspace-settings"
ME = f"{API_PREFIX}/auth/me"

SECRET_MARKERS = (
    "jwt_secret_key",
    "telegram_bot_token",
    "aliexpress_app_secret",
    "aliexpress_app_key",
    "openai_api_key",
    "gemini_api_key",
    "database_url",
    "postgres_password",
)

SENTINEL_SECRET = "task14-never-return-this-secret-value"


def _assert_no_secrets(payload: object) -> None:
    blob = json.dumps(payload)
    for marker in SECRET_MARKERS:
        assert marker not in blob
    assert SENTINEL_SECRET not in blob

    def walk(obj: object) -> None:
        if isinstance(obj, dict):
            for key, value in obj.items():
                assert key not in SECRET_MARKERS
                walk(value)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(payload)


def _headers(token: str, workspace_id: str | None = None) -> dict[str, str]:
    headers = auth_headers(token)
    if workspace_id is not None:
        headers[WORKSPACE_ID_HEADER] = workspace_id
    return headers


def _install_sentinel_secrets(monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "telegram_bot_token", SENTINEL_SECRET)
    monkeypatch.setattr(settings, "openai_api_key", SENTINEL_SECRET)
    monkeypatch.setattr(settings, "gemini_api_key", SENTINEL_SECRET)
    monkeypatch.setattr(settings, "aliexpress_app_key", SENTINEL_SECRET)
    monkeypatch.setattr(settings, "aliexpress_app_secret", SENTINEL_SECRET)
    monkeypatch.setattr(settings, "jwt_secret_key", SENTINEL_SECRET)


@pytest.mark.asyncio
async def test_get_requires_auth(client):
    response = await client.get(SETTINGS)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_requires_workspace_header(client):
    _, token = await register_and_login(client, role="affiliate")
    response = await client.get(SETTINGS, headers=auth_headers(token))
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_empty_defaults_and_hides_secrets(client, monkeypatch):
    _install_sentinel_secrets(monkeypatch)
    _, token = await register_and_login(client, role="affiliate")
    headers = await workspace_auth_headers(token)
    response = await client.get(SETTINGS, headers=headers)
    assert response.status_code == 200
    body = response.json()
    _assert_no_secrets(body)
    assert body["can_edit"] is True
    assert body["timezone"] == "UTC"
    assert set(body["connections"]) == {
        "aliexpress",
        "telegram_bot",
        "openai",
        "gemini",
        "image_search",
    }
    assert all(isinstance(value, bool) for value in body["connections"].values())
    assert body["connections"]["telegram_bot"] is True
    assert body["connections"]["openai"] is True


@pytest.mark.asyncio
async def test_owner_patch_upserts_and_unknown_fields_are_422(client):
    _, token = await register_and_login(client, role="affiliate")
    headers = await workspace_auth_headers(token)

    forbidden = await client.patch(
        SETTINGS,
        headers=headers,
        json={"timezone": "UTC", "jwt_secret_key": "nope"},
    )
    assert forbidden.status_code == 422

    patched = await client.patch(
        SETTINGS,
        headers=headers,
        json={"timezone": "Asia/Jerusalem", "ui_language": "en"},
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    _assert_no_secrets(body)
    assert body["timezone"] == "Asia/Jerusalem"
    assert body["ui_language"] == "en"

    fetched = await client.get(SETTINGS, headers=headers)
    assert fetched.json()["timezone"] == "Asia/Jerusalem"


@pytest.mark.asyncio
async def test_member_patch_is_403(client):
    _, owner_token = await register_and_login(client, role="affiliate")
    owner_headers = await workspace_auth_headers(owner_token)
    workspace_id = owner_headers[WORKSPACE_ID_HEADER]

    _, member_token = await register_and_login(client, role="affiliate")
    await add_workspace_member(member_token, workspace_id)
    member_headers = _headers(member_token, workspace_id)

    readable = await client.get(SETTINGS, headers=member_headers)
    assert readable.status_code == 200
    assert readable.json()["can_edit"] is False

    denied = await client.patch(
        SETTINGS,
        headers=member_headers,
        json={"timezone": "Europe/Paris"},
    )
    assert denied.status_code == 403

    owner_view = await client.get(SETTINGS, headers=owner_headers)
    assert owner_view.json()["timezone"] == "UTC"


@pytest.mark.asyncio
async def test_cross_workspace_patch_is_404(client):
    _, token_a = await register_and_login(client, role="affiliate")
    headers_a = await workspace_auth_headers(token_a)
    await client.patch(
        SETTINGS,
        headers=headers_a,
        json={"ui_language": "en"},
    )

    _, token_b = await register_and_login(client, role="affiliate")
    workspace_b = await _create_workspace_for_user(token_b, name="Other WS")

    leaked = await client.patch(
        SETTINGS,
        headers=_headers(token_a, workspace_b),
        json={"ui_language": "ar"},
    )
    assert leaked.status_code == 404
    assert leaked.json()["detail"] == "Workspace settings not found"

    missing = await client.patch(
        SETTINGS,
        headers=_headers(token_a, str(uuid4())),
        json={"ui_language": "ar"},
    )
    assert missing.status_code == 404

    still_a = await client.get(SETTINGS, headers=headers_a)
    assert still_a.json()["ui_language"] == "en"


@pytest.mark.asyncio
async def test_admin_can_patch_named_workspace(client):
    _, owner_token = await register_and_login(client, role="affiliate")
    owner_headers = await workspace_auth_headers(owner_token)
    workspace_id = owner_headers[WORKSPACE_ID_HEADER]

    _, admin_token = await register_and_login(client, role="admin")
    patched = await client.patch(
        SETTINGS,
        headers=_headers(admin_token, workspace_id),
        json={"discovery_page_size": 10},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["discovery_page_size"] == 10
    assert patched.json()["can_edit"] is True


@pytest.mark.asyncio
async def test_profile_patch_updates_name_not_role(client):
    email, token = await register_and_login(client, role="affiliate")
    headers = auth_headers(token)

    role_attempt = await client.patch(
        ME,
        headers=headers,
        json={"full_name": "Hacker", "role": UserRole.ADMIN.value},
    )
    assert role_attempt.status_code == 422

    active_attempt = await client.patch(
        ME,
        headers=headers,
        json={"is_active": False},
    )
    assert active_attempt.status_code == 422

    updated = await client.patch(
        ME,
        headers=headers,
        json={"full_name": "New Name"},
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["full_name"] == "New Name"
    assert body["role"] == UserRole.AFFILIATE.value
    assert body["is_active"] is True
    assert body["email"] == email

    me = await client.get(ME, headers=headers)
    assert me.json()["full_name"] == "New Name"
    assert me.json()["role"] == UserRole.AFFILIATE.value
