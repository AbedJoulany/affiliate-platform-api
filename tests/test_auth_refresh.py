"""Phase D Task 2 — refresh token lifecycle tests."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.auth.security import (
    decode_access_token,
    generate_refresh_token,
    hash_refresh_token,
)
from app.core.config import get_settings
from app.models.refresh_token import RefreshToken
from tests.conftest import SessionLocal, provision_test_user

API_PREFIX = "/api/v1"
PASSWORD = "StrongP@ssw0rd"


def _assert_tokens_differ(left: str, right: str) -> None:
    assert left != right


def _assert_not_substring(haystack: str, needle: str) -> None:
    assert needle not in haystack


async def _register_and_login(client) -> tuple[str, str, str]:
    email = f"rt-{uuid4().hex[:10]}@example.com"
    await provision_test_user(
        email=email,
        password=PASSWORD,
        full_name="Refresh Token User",
        role="affiliate",
    )
    response = await client.post(
        f"{API_PREFIX}/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert "refresh_token" in body
    assert isinstance(body["refresh_token"], str)
    assert len(body["refresh_token"]) >= 32
    return email, body["access_token"], body["refresh_token"]


# --- A. Token generation ---


def test_generate_refresh_token_is_opaque_and_unpredictable():
    first = generate_refresh_token()
    second = generate_refresh_token()
    assert isinstance(first, str)
    assert len(first) >= 32
    _assert_tokens_differ(first, second)


def test_hash_refresh_token_is_sha256_hex_and_deterministic():
    raw = generate_refresh_token()
    digest = hash_refresh_token(raw)
    assert digest == sha256(raw.encode("utf-8")).hexdigest()
    assert len(digest) == 64
    assert digest == hash_refresh_token(raw)
    assert digest != raw


# --- B. Login ---


@pytest.mark.asyncio
async def test_login_returns_access_and_refresh_and_persists_hash_only(client):
    _, access_token, refresh_token = await _register_and_login(client)
    payload = decode_access_token(access_token)
    assert payload["type"] == "access"

    token_hash = hash_refresh_token(refresh_token)
    async with SessionLocal() as session:
        result = await session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        record = result.scalar_one()
        assert record.revoked_at is None
        assert record.replaced_by_id is None
        settings = get_settings()
        expected_ttl = timedelta(days=settings.refresh_token_expire_days)
        delta = record.expires_at - record.created_at
        assert abs(delta - expected_ttl) < timedelta(seconds=5)

        all_rows = (await session.execute(select(RefreshToken))).scalars().all()
        for row in all_rows:
            _assert_not_substring(row.token_hash, refresh_token)
            assert row.token_hash != refresh_token


# --- C–E. Refresh success, single-use, reuse detection ---


@pytest.mark.asyncio
async def test_refresh_rotates_links_replaced_by_and_is_single_use(client):
    _, _, refresh_token = await _register_and_login(client)

    first = await client.post(
        f"{API_PREFIX}/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert first.status_code == 200
    first_body = first.json()
    assert "access_token" in first_body
    assert "refresh_token" in first_body
    assert first_body["token_type"] == "bearer"
    new_refresh = first_body["refresh_token"]
    _assert_tokens_differ(refresh_token, new_refresh)

    old_hash = hash_refresh_token(refresh_token)
    new_hash = hash_refresh_token(new_refresh)
    async with SessionLocal() as session:
        old = (
            await session.execute(
                select(RefreshToken).where(RefreshToken.token_hash == old_hash)
            )
        ).scalar_one()
        new = (
            await session.execute(
                select(RefreshToken).where(RefreshToken.token_hash == new_hash)
            )
        ).scalar_one()
        assert old.revoked_at is not None
        assert old.replaced_by_id == new.id
        assert new.revoked_at is None
        assert new.replaced_by_id is None

    second = await client.post(
        f"{API_PREFIX}/auth/refresh",
        json={"refresh_token": new_refresh},
    )
    assert second.status_code == 200
    _assert_tokens_differ(new_refresh, second.json()["refresh_token"])

    replay = await client.post(
        f"{API_PREFIX}/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert replay.status_code == 401
    assert "refresh_token" not in replay.json()
    detail = str(replay.json().get("detail", ""))
    _assert_not_substring(detail, refresh_token)
    _assert_not_substring(detail, old_hash)


@pytest.mark.asyncio
async def test_reuse_detection_revokes_all_active_user_tokens(client):
    _, _, refresh_a = await _register_and_login(client)

    rotated = await client.post(
        f"{API_PREFIX}/auth/refresh",
        json={"refresh_token": refresh_a},
    )
    assert rotated.status_code == 200
    refresh_b = rotated.json()["refresh_token"]

    reuse = await client.post(
        f"{API_PREFIX}/auth/refresh",
        json={"refresh_token": refresh_a},
    )
    assert reuse.status_code == 401
    assert "access_token" not in reuse.json()
    assert "refresh_token" not in reuse.json()

    follow_up = await client.post(
        f"{API_PREFIX}/auth/refresh",
        json={"refresh_token": refresh_b},
    )
    assert follow_up.status_code == 401

    async with SessionLocal() as session:
        rows = list((await session.execute(select(RefreshToken))).scalars().all())
        user_rows = [r for r in rows if r.token_hash in {
            hash_refresh_token(refresh_a),
            hash_refresh_token(refresh_b),
        }]
        assert user_rows
        for row in user_rows:
            assert row.revoked_at is not None or row.replaced_by_id is not None


# --- F. Expiration ---


@pytest.mark.asyncio
async def test_expired_refresh_token_is_rejected(client):
    email = f"exp-{uuid4().hex[:10]}@example.com"
    user = await provision_test_user(
        email=email,
        password=PASSWORD,
        full_name="Expired Token User",
        role="affiliate",
    )
    login = await client.post(
        f"{API_PREFIX}/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    assert login.status_code == 200
    refresh_token = login.json()["refresh_token"]
    token_hash = hash_refresh_token(refresh_token)

    async with SessionLocal() as session:
        record = (
            await session.execute(
                select(RefreshToken).where(RefreshToken.token_hash == token_hash)
            )
        ).scalar_one()
        record.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        await session.commit()

    response = await client.post(
        f"{API_PREFIX}/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 401
    assert "access_token" not in response.json()
    assert "refresh_token" not in response.json()

    async with SessionLocal() as session:
        record = (
            await session.execute(
                select(RefreshToken).where(RefreshToken.token_hash == token_hash)
            )
        ).scalar_one()
        assert record.replaced_by_id is None
        # Expired path must not mint a replacement; revoke may be unset.
        assert user.id == record.user_id


# --- G. Invalid token ---


@pytest.mark.asyncio
async def test_nonexistent_refresh_token_is_rejected_without_leak(client):
    bogus = generate_refresh_token()
    response = await client.post(
        f"{API_PREFIX}/auth/refresh",
        json={"refresh_token": bogus},
    )
    assert response.status_code == 401
    body = response.json()
    assert "access_token" not in body
    assert "refresh_token" not in body
    detail = str(body.get("detail", ""))
    _assert_not_substring(detail, bogus)
    _assert_not_substring(detail, hash_refresh_token(bogus))


# --- H. Logout ---


@pytest.mark.asyncio
async def test_logout_revokes_token_and_blocks_refresh(client):
    email_a, _, refresh_a = await _register_and_login(client)
    email_b, _, refresh_b = await _register_and_login(client)
    assert email_a != email_b

    logout = await client.post(
        f"{API_PREFIX}/auth/logout",
        json={"refresh_token": refresh_a},
    )
    assert logout.status_code == 204

    blocked = await client.post(
        f"{API_PREFIX}/auth/refresh",
        json={"refresh_token": refresh_a},
    )
    assert blocked.status_code == 401

    still_ok = await client.post(
        f"{API_PREFIX}/auth/refresh",
        json={"refresh_token": refresh_b},
    )
    assert still_ok.status_code == 200

    # Idempotent logout of already-revoked token
    again = await client.post(
        f"{API_PREFIX}/auth/logout",
        json={"refresh_token": refresh_a},
    )
    assert again.status_code == 204

    missing = await client.post(
        f"{API_PREFIX}/auth/logout",
        json={"refresh_token": generate_refresh_token()},
    )
    assert missing.status_code == 204


# --- I. Access / refresh separation ---


@pytest.mark.asyncio
async def test_access_token_still_works_and_refresh_cannot_auth_me(client):
    _, access_token, refresh_token = await _register_and_login(client)

    me = await client.get(
        f"{API_PREFIX}/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me.status_code == 200

    spoof = await client.get(
        f"{API_PREFIX}/auth/me",
        headers={"Authorization": f"Bearer {refresh_token}"},
    )
    assert spoof.status_code == 401


# --- K. Concurrent / double-use rotation ---


@pytest.mark.asyncio
async def test_concurrent_refresh_allows_at_most_one_success(client):
    _, _, refresh_token = await _register_and_login(client)

    first, second = await asyncio.gather(
        client.post(
            f"{API_PREFIX}/auth/refresh",
            json={"refresh_token": refresh_token},
        ),
        client.post(
            f"{API_PREFIX}/auth/refresh",
            json={"refresh_token": refresh_token},
        ),
    )
    statuses = sorted([first.status_code, second.status_code])
    # One rotation wins; the other is rejected (401). SQLite may serialize as
    # 200/401; never allow two successful rotations of the same token.
    assert statuses in ([200, 401], [401, 401])
    successes = [r for r in (first, second) if r.status_code == 200]
    assert len(successes) <= 1
    if len(successes) == 1:
        body = successes[0].json()
        assert "access_token" in body
        assert "refresh_token" in body
        _assert_tokens_differ(refresh_token, body["refresh_token"])
