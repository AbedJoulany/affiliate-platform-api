"""Phase D Task 3 — Redis fixed-window rate limiting."""

from __future__ import annotations

from uuid import uuid4

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
from starlette.requests import Request

from app.auth.security import generate_refresh_token
from app.core.rate_limit import (
    CONVERSION_LIMIT,
    CONVERSION_WINDOW_SECONDS,
    LOGIN_LIMIT,
    LOGIN_WINDOW_SECONDS,
    REFRESH_LIMIT,
    REFRESH_WINDOW_SECONDS,
    build_rate_limit_key,
    increment_fixed_window,
    limit_auth_login,
    limit_auth_refresh,
    limit_conversions,
    resolve_identity,
)
from app.main import app as fastapi_app
from tests.conftest import provision_test_user

API_PREFIX = "/api/v1"
PASSWORD = "StrongP@ssw0rd"


class FakeRedis:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.ttls: dict[str, int] = {}
        self.expire_calls: list[tuple[str, int]] = []

    async def incr(self, key: str) -> int:
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key: str, seconds: int) -> bool:
        self.expire_calls.append((key, seconds))
        self.ttls[key] = seconds
        return True

    async def ttl(self, key: str) -> int:
        if key not in self.counts:
            return -2
        return self.ttls.get(key, -1)


class _FailingRedis:
    def __init__(self, exc: BaseException) -> None:
        self.exc = exc

    async def incr(self, key: str) -> int:
        raise self.exc


def _fake_request(*, host: str = "203.0.113.10") -> Request:
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": [],
            "client": (host, 12345),
            "server": ("test", 80),
        }
    )


def _walk_calls(dependant):
    for dep in dependant.dependencies:
        if dep.call is not None:
            yield dep.call
        yield from _walk_calls(dep)


def _iter_api_routes():
    from fastapi.routing import APIRoute

    def walk(router, prefix: str = ""):
        for route in router.routes:
            if isinstance(route, APIRoute):
                yield prefix + route.path, route
            elif type(route).__name__ == "_IncludedRouter":
                nested = prefix + (route.include_context.prefix or "")
                yield from walk(route.original_router, nested)

    yield from walk(fastapi_app.router)


def _route_calls(path: str, method: str) -> list:
    for full_path, route in _iter_api_routes():
        if full_path == path and method in (route.methods or set()):
            return list(_walk_calls(route.dependant))
    raise AssertionError(f"route not found: {method} {path}")


def _rate_limit_routes_on(path: str, method: str) -> set[str]:
    found: set[str] = set()
    for call in _route_calls(path, method):
        route_id = getattr(call, "__rate_limit_route__", None)
        if route_id is not None:
            found.add(route_id)
    return found


@pytest.fixture
def fake_redis(monkeypatch) -> FakeRedis:
    store = FakeRedis()

    async def _get_fake():
        return store

    monkeypatch.setattr("app.core.rate_limit.get_rate_limit_redis", _get_fake)
    return store


def _conversion_payload() -> dict:
    return {
        "affiliate_id": str(uuid4()),
        "campaign_id": str(uuid4()),
        "external_order_id": f"order-{uuid4().hex[:8]}",
        "amount": 10.0,
        "currency": "USD",
    }


@pytest.mark.asyncio
async def test_increment_sets_ttl_only_on_first_request():
    redis = FakeRedis()
    key = "ratelimit:login:ip:203.0.113.10:300"
    first_count, first_ttl = await increment_fixed_window(redis, key, 300)
    assert first_count == 1
    assert first_ttl == 300
    assert redis.expire_calls == [(key, 300)]

    second_count, second_ttl = await increment_fixed_window(redis, key, 300)
    assert second_count == 2
    assert second_ttl == 300
    assert redis.expire_calls == [(key, 300)]


@pytest.mark.asyncio
async def test_increment_allows_up_to_limit_then_exceeds():
    redis = FakeRedis()
    key = "ratelimit:login:ip:203.0.113.10:300"
    for expected in range(1, LOGIN_LIMIT + 1):
        count, _ = await increment_fixed_window(redis, key, LOGIN_WINDOW_SECONDS)
        assert count == expected
        assert count <= LOGIN_LIMIT
    over, _ = await increment_fixed_window(redis, key, LOGIN_WINDOW_SECONDS)
    assert over == LOGIN_LIMIT + 1


def test_task_0_policy_constants():
    assert LOGIN_LIMIT == 10
    assert LOGIN_WINDOW_SECONDS == 300
    assert REFRESH_LIMIT == 20
    assert REFRESH_WINDOW_SECONDS == 300
    assert CONVERSION_LIMIT == 30
    assert CONVERSION_WINDOW_SECONDS == 60


def test_login_and_refresh_identity_is_client_ip_not_forwarded_header():
    request = Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": [
                (b"x-forwarded-for", b"198.51.100.1"),
                (b"x-real-ip", b"198.51.100.2"),
            ],
            "client": ("203.0.113.10", 12345),
            "server": ("test", 80),
        }
    )
    kind, identity = resolve_identity(request, "ip")
    assert kind == "ip"
    assert identity == "203.0.113.10"
    assert identity != "198.51.100.1"
    assert identity != "198.51.100.2"


def test_conversion_falls_back_to_ip_without_user():
    kind, identity = resolve_identity(_fake_request(), "user_or_ip")
    assert kind == "ip"
    assert identity == "203.0.113.10"


def test_rate_limit_keys_are_isolated_by_route_and_identity():
    login_a = build_rate_limit_key(
        route="login", identity_kind="ip", identity="203.0.113.10", window_seconds=300
    )
    login_b = build_rate_limit_key(
        route="login", identity_kind="ip", identity="198.51.100.20", window_seconds=300
    )
    refresh_a = build_rate_limit_key(
        route="refresh", identity_kind="ip", identity="203.0.113.10", window_seconds=300
    )
    conv_ip = build_rate_limit_key(
        route="conversions",
        identity_kind="ip",
        identity="203.0.113.10",
        window_seconds=60,
    )
    conv_user = build_rate_limit_key(
        route="conversions",
        identity_kind="user",
        identity="11111111-1111-1111-1111-111111111111",
        window_seconds=60,
    )
    keys = {login_a, login_b, refresh_a, conv_ip, conv_user}
    assert len(keys) == 5
    assert all(key.startswith("ratelimit:") for key in keys)


def test_rate_limit_key_does_not_embed_raw_credentials():
    raw = generate_refresh_token()
    key = build_rate_limit_key(
        route="refresh", identity_kind="ip", identity="203.0.113.10", window_seconds=300
    )
    assert raw not in key
    assert "Bearer" not in key


@pytest.mark.asyncio
async def test_login_allows_up_to_limit_then_returns_429(client, fake_redis, caplog):
    for _ in range(LOGIN_LIMIT):
        response = await client.post(
            f"{API_PREFIX}/auth/login",
            data={"username": "nobody@example.com", "password": PASSWORD},
        )
        assert response.status_code == 401

    blocked = await client.post(
        f"{API_PREFIX}/auth/login",
        data={"username": "nobody@example.com", "password": PASSWORD},
    )
    assert blocked.status_code == 429
    assert blocked.json() == {"detail": "Rate limit exceeded"}
    retry_after = blocked.headers.get("retry-after")
    assert retry_after is not None
    assert retry_after.isdigit()
    assert PASSWORD not in caplog.text
    assert PASSWORD not in str(blocked.json())
    assert any(key.startswith("ratelimit:login:ip:") for key in fake_redis.counts)
    assert all("refresh" not in key for key in fake_redis.counts)
    assert fake_redis.expire_calls
    assert fake_redis.expire_calls[0][1] == LOGIN_WINDOW_SECONDS
    assert len(fake_redis.expire_calls) == 1


@pytest.mark.asyncio
async def test_refresh_allows_up_to_limit_then_returns_429(client, fake_redis):
    token = generate_refresh_token()
    for _ in range(REFRESH_LIMIT):
        response = await client.post(
            f"{API_PREFIX}/auth/refresh",
            json={"refresh_token": token},
        )
        assert response.status_code == 401

    blocked = await client.post(
        f"{API_PREFIX}/auth/refresh",
        json={"refresh_token": token},
    )
    assert blocked.status_code == 429
    assert blocked.json() == {"detail": "Rate limit exceeded"}
    assert blocked.headers.get("retry-after") is not None
    assert token not in str(blocked.json())
    assert any(key.startswith("ratelimit:refresh:ip:") for key in fake_redis.counts)
    assert fake_redis.expire_calls[0][1] == REFRESH_WINDOW_SECONDS


@pytest.mark.asyncio
async def test_conversion_allows_up_to_limit_then_returns_429(client, fake_redis):
    for _ in range(CONVERSION_LIMIT):
        response = await client.post(
            f"{API_PREFIX}/conversions",
            json=_conversion_payload(),
        )
        assert response.status_code == 404

    blocked = await client.post(
        f"{API_PREFIX}/conversions",
        json=_conversion_payload(),
    )
    assert blocked.status_code == 429
    assert blocked.json() == {"detail": "Rate limit exceeded"}
    assert any(key.startswith("ratelimit:conversions:ip:") for key in fake_redis.counts)
    assert fake_redis.expire_calls[0][1] == CONVERSION_WINDOW_SECONDS


@pytest.mark.asyncio
async def test_conversion_uses_user_id_when_access_token_present(client, fake_redis):
    email = f"rl-{uuid4().hex[:10]}@example.com"
    await provision_test_user(
        email=email,
        password=PASSWORD,
        full_name="Rate Limit User",
        role="affiliate",
    )
    login = await client.post(
        f"{API_PREFIX}/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    assert login.status_code == 200
    access_token = login.json()["access_token"]
    refresh_token = login.json()["refresh_token"]

    response = await client.post(
        f"{API_PREFIX}/conversions",
        headers={"Authorization": f"Bearer {access_token}"},
        json=_conversion_payload(),
    )
    assert response.status_code == 404
    user_keys = [k for k in fake_redis.counts if k.startswith("ratelimit:conversions:user:")]
    ip_keys = [k for k in fake_redis.counts if k.startswith("ratelimit:conversions:ip:")]
    assert user_keys
    assert not ip_keys
    joined = "".join(fake_redis.counts)
    assert access_token not in joined
    assert refresh_token not in joined


@pytest.mark.asyncio
async def test_conversion_user_buckets_are_isolated(client, fake_redis):
    tokens = []
    for _ in range(2):
        email = f"rl-{uuid4().hex[:10]}@example.com"
        await provision_test_user(
            email=email,
            password=PASSWORD,
            full_name="Rate Limit User",
            role="affiliate",
        )
        login = await client.post(
            f"{API_PREFIX}/auth/login",
            data={"username": email, "password": PASSWORD},
        )
        assert login.status_code == 200
        tokens.append(login.json()["access_token"])

    for token in tokens:
        response = await client.post(
            f"{API_PREFIX}/conversions",
            headers={"Authorization": f"Bearer {token}"},
            json=_conversion_payload(),
        )
        assert response.status_code == 404

    user_keys = [k for k in fake_redis.counts if k.startswith("ratelimit:conversions:user:")]
    assert len(user_keys) == 2
    assert fake_redis.counts[user_keys[0]] == 1
    assert fake_redis.counts[user_keys[1]] == 1


@pytest.mark.asyncio
async def test_login_and_refresh_counters_do_not_collide(client, fake_redis):
    for _ in range(LOGIN_LIMIT):
        response = await client.post(
            f"{API_PREFIX}/auth/login",
            data={"username": "nobody@example.com", "password": PASSWORD},
        )
        assert response.status_code == 401

    refresh = await client.post(
        f"{API_PREFIX}/auth/refresh",
        json={"refresh_token": generate_refresh_token()},
    )
    assert refresh.status_code == 401
    login_keys = [k for k in fake_redis.counts if k.startswith("ratelimit:login:")]
    refresh_keys = [k for k in fake_redis.counts if k.startswith("ratelimit:refresh:")]
    assert login_keys
    assert refresh_keys
    assert set(login_keys).isdisjoint(refresh_keys)


@pytest.mark.asyncio
async def test_redis_connection_failure_allows_login(client, monkeypatch, caplog):
    failing = _FailingRedis(RedisConnectionError("unavailable"))

    async def _get_failing():
        return failing

    monkeypatch.setattr("app.core.rate_limit.get_rate_limit_redis", _get_failing)
    response = await client.post(
        f"{API_PREFIX}/auth/login",
        data={"username": "nobody@example.com", "password": PASSWORD},
    )
    assert response.status_code == 401
    assert PASSWORD not in caplog.text


@pytest.mark.asyncio
async def test_redis_timeout_allows_refresh_without_429(client, monkeypatch, caplog):
    failing = _FailingRedis(RedisTimeoutError("timed out"))

    async def _get_failing():
        return failing

    monkeypatch.setattr("app.core.rate_limit.get_rate_limit_redis", _get_failing)
    token = generate_refresh_token()
    response = await client.post(
        f"{API_PREFIX}/auth/refresh",
        json={"refresh_token": token},
    )
    assert response.status_code == 401
    assert token not in caplog.text


@pytest.mark.asyncio
async def test_successful_login_and_refresh_contract_unchanged(client, fake_redis):
    email = f"rl-{uuid4().hex[:10]}@example.com"
    await provision_test_user(
        email=email,
        password=PASSWORD,
        full_name="Rate Limit User",
        role="affiliate",
    )
    login = await client.post(
        f"{API_PREFIX}/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    assert login.status_code == 200
    body = login.json()
    assert set(body) >= {"access_token", "token_type", "refresh_token"}
    assert body["token_type"] == "bearer"

    refreshed = await client.post(
        f"{API_PREFIX}/auth/refresh",
        json={"refresh_token": body["refresh_token"]},
    )
    assert refreshed.status_code == 200
    assert set(refreshed.json()) >= {"access_token", "token_type", "refresh_token"}


@pytest.mark.asyncio
async def test_conversion_validation_unchanged_under_limiter(client, fake_redis):
    response = await client.post(f"{API_PREFIX}/conversions", json={"amount": 1})
    assert response.status_code == 422


def test_rate_limit_dependency_only_on_selected_routes():
    assert _rate_limit_routes_on(f"{API_PREFIX}/auth/login", "POST") == {"login"}
    assert _rate_limit_routes_on(f"{API_PREFIX}/auth/refresh", "POST") == {"refresh"}
    assert _rate_limit_routes_on(f"{API_PREFIX}/conversions", "POST") == {"conversions"}
    assert _rate_limit_routes_on(f"{API_PREFIX}/queues/stream", "GET") == set()
    assert _rate_limit_routes_on("/health", "GET") == set()
    assert _rate_limit_routes_on("/ready", "GET") == set()
    assert _rate_limit_routes_on("/worker/health", "GET") == set()
    assert limit_auth_login.__rate_limit_route__ == "login"
    assert limit_auth_refresh.__rate_limit_route__ == "refresh"
    assert limit_conversions.__rate_limit_route__ == "conversions"


def test_no_global_rate_limit_middleware():
    names = [type(middleware.cls).__name__ for middleware in fastapi_app.user_middleware]
    assert "BaseHTTPMiddleware" not in names
    assert not any("rate" in name.lower() for name in names)
