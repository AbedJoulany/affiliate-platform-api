"""Redis-backed fixed-window rate limiting as a FastAPI dependency factory.

Applied only to the three Phase D Task 0 routes via ``Depends(...)``.
Not middleware — SSE and other routes are untouched unless explicitly wired.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Coroutine
from typing import Any, Literal

from fastapi import HTTPException, Request, status
from redis import asyncio as redis
from redis.exceptions import RedisError

from app.core.config import get_settings

logger = logging.getLogger(__name__)

LOGIN_LIMIT = 10
LOGIN_WINDOW_SECONDS = 5 * 60
REFRESH_LIMIT = 20
REFRESH_WINDOW_SECONDS = 5 * 60
CONVERSION_LIMIT = 30
CONVERSION_WINDOW_SECONDS = 60

_IDENTITY_SAFE = re.compile(r"[^A-Za-z0-9._-]+")
_REDIS_CONNECT_TIMEOUT_SECONDS = 1.0

IdentityMode = Literal["ip", "user_or_ip"]

_redis_client: Any | None = None


async def get_rate_limit_redis() -> Any:
    """Return a process-local Redis client (existing redis-py asyncio client)."""
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = redis.from_url(
            settings.broker_url,
            socket_connect_timeout=_REDIS_CONNECT_TIMEOUT_SECONDS,
            socket_timeout=_REDIS_CONNECT_TIMEOUT_SECONDS,
            decode_responses=True,
        )
    return _redis_client


def _sanitize_identity(value: str) -> str:
    cleaned = _IDENTITY_SAFE.sub("_", value).strip("_")
    return (cleaned or "unknown")[:128]


def _client_ip(request: Request) -> str:
    if request.client is None or not request.client.host:
        return "unknown"
    return request.client.host


def _optional_access_subject(request: Request) -> str | None:
    """Return JWT access-token subject when a valid Bearer access token is present.

    Invalid, missing, or non-access credentials fall back to IP. Does not
    authenticate the route and does not raise.
    """
    authorization = request.headers.get("Authorization")
    if not authorization:
        return None
    scheme, _, credentials = authorization.partition(" ")
    if scheme.lower() != "bearer" or not credentials:
        return None
    from app.auth.security import decode_access_token

    try:
        payload = decode_access_token(credentials)
        subject = payload.get("sub")
    except (ValueError, KeyError):
        return None
    if not isinstance(subject, str) or not subject:
        return None
    return subject


def resolve_identity(request: Request, mode: IdentityMode) -> tuple[str, str]:
    if mode == "user_or_ip":
        subject = _optional_access_subject(request)
        if subject is not None:
            return "user", subject
    return "ip", _client_ip(request)


def build_rate_limit_key(
    *,
    route: str,
    identity_kind: str,
    identity: str,
    window_seconds: int,
) -> str:
    return (
        f"ratelimit:{route}:{identity_kind}:"
        f"{_sanitize_identity(identity)}:{window_seconds}"
    )


async def increment_fixed_window(
    client: Any,
    key: str,
    window_seconds: int,
) -> tuple[int, int]:
    """INCR the counter; EXPIRE only when the key is newly created."""
    count = int(await client.incr(key))
    if count == 1:
        await client.expire(key, window_seconds)
    ttl = int(await client.ttl(key))
    return count, ttl


def rate_limit(
    *,
    route: str,
    limit: int,
    window_seconds: int,
    identity: IdentityMode = "ip",
) -> Callable[[Request], Coroutine[Any, Any, None]]:
    """Return a FastAPI dependency that enforces a fixed-window limit."""

    async def enforce_rate_limit(request: Request) -> None:
        kind, raw_identity = resolve_identity(request, identity)
        key = build_rate_limit_key(
            route=route,
            identity_kind=kind,
            identity=raw_identity,
            window_seconds=window_seconds,
        )
        try:
            client = await get_rate_limit_redis()
            count, ttl = await increment_fixed_window(client, key, window_seconds)
        except HTTPException:
            raise
        except RedisError as exc:
            logger.warning(
                "Rate limiter Redis failure; allowing request route=%s error=%s",
                route,
                type(exc).__name__,
            )
            return
        except (TimeoutError, OSError, ConnectionError) as exc:
            logger.warning(
                "Rate limiter Redis failure; allowing request route=%s error=%s",
                route,
                type(exc).__name__,
            )
            return

        if count <= limit:
            return

        retry_after = ttl if ttl > 0 else window_seconds
        logger.warning(
            "Rate limit exceeded route=%s limit=%s window_seconds=%s",
            route,
            limit,
            window_seconds,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )

    enforce_rate_limit.__rate_limit_route__ = route  # type: ignore[attr-defined]
    return enforce_rate_limit


limit_auth_login = rate_limit(
    route="login",
    limit=LOGIN_LIMIT,
    window_seconds=LOGIN_WINDOW_SECONDS,
    identity="ip",
)
limit_auth_refresh = rate_limit(
    route="refresh",
    limit=REFRESH_LIMIT,
    window_seconds=REFRESH_WINDOW_SECONDS,
    identity="ip",
)
limit_conversions = rate_limit(
    route="conversions",
    limit=CONVERSION_LIMIT,
    window_seconds=CONVERSION_WINDOW_SECONDS,
    identity="user_or_ip",
)
