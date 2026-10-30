from __future__ import annotations

import base64
import json
from uuid import UUID

import pytest

from app.core.config import get_settings
from app.core.workspace import WORKSPACE_ID_HEADER
from app.facebook.client import FacebookGraphClient, FacebookGraphError, FacebookPageIdentity
from app.facebook.crypto import FacebookTokenCipher, FacebookTokenEncryptionError
from app.models.facebook_page import FacebookPage
from tests.conftest import SessionLocal
from tests.test_api_endpoints import (
    API_PREFIX,
    auth_headers,
    register_and_login,
    workspace_auth_headers,
)

PAGES = f"{API_PREFIX}/facebook/pages"


def _headers(token: str, workspace_id: str | None = None) -> dict[str, str]:
    headers = auth_headers(token)
    if workspace_id:
        headers[WORKSPACE_ID_HEADER] = workspace_id
    return headers


def _key() -> str:
    return base64.urlsafe_b64encode(b"facebook-test-key-32-bytes-long!").decode()


@pytest.fixture
def mock_facebook_graph(monkeypatch):
    async def validate_page(self, page_id: str, access_token: str) -> FacebookPageIdentity:
        if access_token == "expired-token":
            raise FacebookGraphError(
                "Facebook credentials are invalid or lack access to this Page",
                status_code=422,
            )
        return FacebookPageIdentity(page_id=page_id, name="Test Facebook Page")

    monkeypatch.setattr("app.facebook.client.FacebookGraphClient.validate_page", validate_page)


@pytest.mark.asyncio
async def test_facebook_pages_require_auth_and_workspace(client):
    assert (await client.get(PAGES)).status_code == 401
    _, token = await register_and_login(client, role="user")
    assert (await client.get(PAGES, headers=auth_headers(token))).status_code == 403


@pytest.mark.asyncio
async def test_create_page_validates_and_never_returns_token(
    client, monkeypatch, mock_facebook_graph
):
    monkeypatch.setattr(get_settings(), "facebook_token_encryption_key", _key())
    _, token = await register_and_login(client, role="user")
    headers = await workspace_auth_headers(token)
    secret = "page-token-never-return-this"

    response = await client.post(
        PAGES,
        headers=headers,
        json={"facebook_page_id": "123456", "access_token": secret},
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["page_name"] == "Test Facebook Page"
    assert payload["validation_status"] == "valid"
    assert payload["has_access_token"] is True
    assert secret not in json.dumps(payload)
    assert "encrypted_access_token" not in payload
    assert "access_token" not in payload
    async with SessionLocal() as session:
        stored = await session.get(FacebookPage, UUID(payload["id"]))
        assert stored is not None
        assert secret not in stored.encrypted_access_token


@pytest.mark.asyncio
async def test_duplicate_page_and_invalid_token_are_rejected(
    client, monkeypatch, mock_facebook_graph
):
    monkeypatch.setattr(get_settings(), "facebook_token_encryption_key", _key())
    _, token = await register_and_login(client, role="user")
    headers = await workspace_auth_headers(token)
    body = {"facebook_page_id": "123457", "access_token": "valid-token"}
    first = await client.post(PAGES, headers=headers, json=body)
    assert first.status_code == 201
    duplicate = await client.post(PAGES, headers=headers, json=body)
    assert duplicate.status_code == 409

    invalid = await client.post(
        PAGES,
        headers=headers,
        json={"facebook_page_id": "123458", "access_token": "expired-token"},
    )
    assert invalid.status_code == 422


@pytest.mark.asyncio
async def test_members_can_read_but_only_owner_can_change_page(
    client, monkeypatch, mock_facebook_graph
):
    monkeypatch.setattr(get_settings(), "facebook_token_encryption_key", _key())
    _, owner_token = await register_and_login(client, role="user")
    owner_headers = await workspace_auth_headers(owner_token)
    workspace_id = owner_headers[WORKSPACE_ID_HEADER]
    created = await client.post(
        PAGES,
        headers=owner_headers,
        json={"facebook_page_id": "123459", "access_token": "valid-token"},
    )
    page_id = created.json()["id"]

    _, member_token = await register_and_login(client, role="user")
    from tests.test_api_endpoints import add_workspace_member

    await add_workspace_member(member_token, workspace_id)
    member_headers = _headers(member_token, workspace_id)
    assert (await client.get(PAGES, headers=member_headers)).status_code == 200
    denied = await client.patch(
        f"{PAGES}/{page_id}",
        headers=member_headers,
        json={"is_active": False},
    )
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_token_replacement_validates_before_replacing(
    client, monkeypatch, mock_facebook_graph
):
    monkeypatch.setattr(get_settings(), "facebook_token_encryption_key", _key())
    _, token = await register_and_login(client, role="user")
    headers = await workspace_auth_headers(token)
    created = await client.post(
        PAGES,
        headers=headers,
        json={"facebook_page_id": "123460", "access_token": "old-token"},
    )
    page_id = created.json()["id"]
    failed = await client.patch(
        f"{PAGES}/{page_id}",
        headers=headers,
        json={"access_token": "expired-token"},
    )
    assert failed.status_code == 422
    validated = await client.post(f"{PAGES}/{page_id}/validate", headers=headers)
    assert validated.status_code == 200
    assert validated.json()["validation_status"] == "valid"


@pytest.mark.asyncio
async def test_missing_encryption_configuration_fails_closed(
    client, monkeypatch, mock_facebook_graph
):
    monkeypatch.setattr(get_settings(), "facebook_token_encryption_key", None)
    _, token = await register_and_login(client, role="user")
    headers = await workspace_auth_headers(token)
    response = await client.post(
        PAGES,
        headers=headers,
        json={"facebook_page_id": "123461", "access_token": "valid-token"},
    )
    assert response.status_code == 503


class _FakeHttpClient:
    def __init__(self, response):
        self.response = response

    async def get(self, *args, **kwargs):
        return self.response


@pytest.mark.asyncio
async def test_graph_client_sanitizes_rate_limit_and_invalid_responses():
    from httpx import Response

    client = FacebookGraphClient(
        http_client=_FakeHttpClient(Response(429, json={"access_token": "secret"}))
    )
    with pytest.raises(FacebookGraphError, match="rate limit"):
        await client.validate_page("123", "secret")
    client = FacebookGraphClient(
        http_client=_FakeHttpClient(Response(200, json={"id": "123"}))
    )
    with pytest.raises(FacebookGraphError, match="invalid Page response"):
        await client.validate_page("123", "secret")


def test_token_cipher_round_trip_and_fail_closed():
    cipher = FacebookTokenCipher(_key())
    unpadded_cipher = FacebookTokenCipher(_key().rstrip("="))
    token = "secret-token"
    encrypted = cipher.encrypt(token)
    assert encrypted != token
    assert cipher.decrypt(encrypted) == token
    assert unpadded_cipher.decrypt(unpadded_cipher.encrypt(token)) == token
    with pytest.raises(FacebookTokenEncryptionError):
        FacebookTokenCipher(None)
    with pytest.raises(FacebookTokenEncryptionError):
        cipher.decrypt(encrypted[:-2] + "xx")
