from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.enums import (
    AIProviderType,
    ContentLanguage,
    ContentLength,
    ContentType,
    ToneProfile,
)
from app.schemas.automation_content import AutomationContentPreviewRequest
from app.services.automation_content import (
    AutomationContentGenerationService,
    EffectiveContentPreferences,
)
from app.services.exceptions import ConflictError


def _payload(key: str) -> AutomationContentPreviewRequest:
    return AutomationContentPreviewRequest(
        expected_policy_revision=1,
        max_products=1,
        acknowledge_ai_cost=True,
        idempotency_key=key,
    )


def _preferences() -> EffectiveContentPreferences:
    return EffectiveContentPreferences(
        provider=AIProviderType.OPENAI,
        language=ContentLanguage.AR,
        tone=ToneProfile.PERSUASIVE,
        content_type=ContentType.TELEGRAM,
        length=ContentLength.MEDIUM,
    )


@pytest.fixture
async def isolated_redis():
    url = os.getenv("PHASE7B_REDIS_URL")
    if not url:
        if os.getenv("PHASE7B_REDIS_REQUIRED") == "1":
            pytest.fail("PHASE7B_REDIS_URL is required for this verification job")
        pytest.skip("PHASE7B_REDIS_URL is not configured")
    client = Redis.from_url(url, decode_responses=True)
    try:
        await client.ping()
    except RedisError as exc:
        await client.aclose()
        pytest.skip(f"isolated Redis is unavailable: {exc.__class__.__name__}")
    try:
        yield client
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_real_redis_suppresses_equivalent_requests_with_different_keys(
    isolated_redis,
    monkeypatch,
):
    async def get_redis():
        return isolated_redis

    monkeypatch.setattr(
        "app.services.automation_content.get_automation_generation_redis",
        get_redis,
    )
    service = AutomationContentGenerationService(None)
    policy = SimpleNamespace(revision=1)
    workspace_id = uuid4()
    user_id = uuid4()
    first = await service._claim_duplicate_guard(
        user_id=user_id,
        workspace_id=workspace_id,
        policy=policy,
        payload=_payload("real-redis-equivalent-1"),
        preferences=_preferences(),
    )
    try:
        with pytest.raises(ConflictError, match="Equivalent"):
            await service._claim_duplicate_guard(
                user_id=user_id,
                workspace_id=workspace_id,
                policy=policy,
                payload=_payload("real-redis-equivalent-2"),
                preferences=_preferences(),
            )
    finally:
        await service._release_guard(first)


@pytest.mark.asyncio
async def test_real_redis_concurrent_equivalent_claims_have_one_owner(
    isolated_redis,
    monkeypatch,
):
    async def get_redis():
        return isolated_redis

    monkeypatch.setattr(
        "app.services.automation_content.get_automation_generation_redis",
        get_redis,
    )
    service = AutomationContentGenerationService(None)
    policy = SimpleNamespace(revision=1)
    workspace_id = uuid4()
    user_id = uuid4()

    async def claim(key: str):
        try:
            return await service._claim_duplicate_guard(
                user_id=user_id,
                workspace_id=workspace_id,
                policy=policy,
                payload=_payload(key),
                preferences=_preferences(),
            )
        except ConflictError:
            return None

    claims = await asyncio.gather(
        claim("real-redis-concurrent-1"),
        claim("real-redis-concurrent-2"),
    )
    owners = [item for item in claims if item is not None]
    assert len(owners) == 1
    await service._release_guard(owners[0])


@pytest.mark.asyncio
async def test_real_redis_compare_delete_preserves_replaced_owner(
    isolated_redis,
    monkeypatch,
):
    async def get_redis():
        return isolated_redis

    monkeypatch.setattr(
        "app.services.automation_content.get_automation_generation_redis",
        get_redis,
    )
    service = AutomationContentGenerationService(None)
    claim = await service._claim_duplicate_guard(
        user_id=uuid4(),
        workspace_id=uuid4(),
        policy=SimpleNamespace(revision=1),
        payload=_payload("real-redis-owner"),
        preferences=_preferences(),
    )
    try:
        await isolated_redis.set(claim.fingerprint_key, "replacement-owner", ex=30)
        await service._release_guard(claim)
        assert await isolated_redis.get(claim.fingerprint_key) == "replacement-owner"
    finally:
        await isolated_redis.delete(claim.idempotency_key, claim.fingerprint_key)


@pytest.mark.asyncio
async def test_real_redis_expired_guard_allows_new_explicit_request(
    isolated_redis,
    monkeypatch,
):
    async def get_redis():
        return isolated_redis

    monkeypatch.setattr(
        "app.services.automation_content.get_automation_generation_redis",
        get_redis,
    )
    service = AutomationContentGenerationService(None)
    policy = SimpleNamespace(revision=1)
    workspace_id = uuid4()
    user_id = uuid4()
    first = await service._claim_duplicate_guard(
        user_id=user_id,
        workspace_id=workspace_id,
        policy=policy,
        payload=_payload("real-redis-expiry"),
        preferences=_preferences(),
    )
    await isolated_redis.expire(first.idempotency_key, 1)
    await isolated_redis.expire(first.fingerprint_key, 1)
    await asyncio.sleep(1.2)

    second = await service._claim_duplicate_guard(
        user_id=user_id,
        workspace_id=workspace_id,
        policy=policy,
        payload=_payload("real-redis-expiry"),
        preferences=_preferences(),
    )
    await service._release_guard(second)
