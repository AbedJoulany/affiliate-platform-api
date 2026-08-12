"""Focused coverage for AliExpressAPIClient._execute_with_retries."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.aliexpress.api_client import AliExpressAPIClient
from app.aliexpress.exceptions import (
    AliExpressAPIError,
    AliExpressCredentialsError,
    AliExpressRateLimitError,
)
from app.core.config import Settings


def _client(**overrides) -> AliExpressAPIClient:
    values = {
        "aliexpress_app_key": "app-key",
        "aliexpress_app_secret": "app-secret",
        "aliexpress_max_retries": 3,
        "aliexpress_retry_backoff_seconds": 0.5,
        "aliexpress_rate_limit_interval_seconds": 0.0,
    }
    values.update(overrides)
    return AliExpressAPIClient(Settings(**values))


def _request() -> MagicMock:
    return MagicMock(name="iop-request")


@pytest.mark.asyncio
async def test_success_without_retry(monkeypatch):
    client = _client()
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.aliexpress.api_client.asyncio.sleep", fake_sleep)
    client._execute_once = AsyncMock(return_value={"ok": True})
    client._raise_for_top_level_errors = MagicMock()

    payload = await client._execute_with_retries(_request())

    assert payload == {"ok": True}
    assert client._execute_once.await_count == 1
    assert sleeps == []


@pytest.mark.asyncio
async def test_retryable_failure_then_success(monkeypatch):
    client = _client()
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.aliexpress.api_client.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("app.aliexpress.api_client.random.uniform", lambda a, b: 0.1)
    client._execute_once = AsyncMock(
        side_effect=[
            AliExpressAPIError("server error", code=503),
            {"ok": True},
        ]
    )
    client._raise_for_top_level_errors = MagicMock()

    payload = await client._execute_with_retries(_request())

    assert payload == {"ok": True}
    assert client._execute_once.await_count == 2
    assert sleeps == [0.5 * (2**0) + 0.1]


@pytest.mark.asyncio
async def test_exhausted_retry_budget_raises_final_error(monkeypatch):
    client = _client()
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.aliexpress.api_client.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("app.aliexpress.api_client.random.uniform", lambda a, b: 0.0)
    error = AliExpressAPIError("still failing", code=502)
    client._execute_once = AsyncMock(side_effect=error)
    client._raise_for_top_level_errors = MagicMock()

    with pytest.raises(AliExpressAPIError) as exc_info:
        await client._execute_with_retries(_request())

    assert exc_info.value is error
    assert client._execute_once.await_count == 4  # max_retries(3) + 1
    assert len(sleeps) == 3
    assert sleeps == [0.5, 1.0, 2.0]


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [400, 401, 403, 404])
async def test_non_retryable_http_error_does_not_retry(monkeypatch, status_code: int):
    client = _client()
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.aliexpress.api_client.asyncio.sleep", fake_sleep)
    error = AliExpressAPIError("permanent failure", code=status_code)
    client._execute_once = AsyncMock(side_effect=error)
    client._raise_for_top_level_errors = MagicMock()

    with pytest.raises(AliExpressAPIError) as exc_info:
        await client._execute_with_retries(_request())

    assert exc_info.value is error
    assert client._execute_once.await_count == 1
    assert sleeps == []


@pytest.mark.asyncio
async def test_rate_limit_error_retries_with_backoff(monkeypatch):
    client = _client()
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.aliexpress.api_client.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("app.aliexpress.api_client.random.uniform", lambda a, b: 0.05)
    client._execute_once = AsyncMock(
        side_effect=[
            AliExpressRateLimitError("rate limited", code=429),
            {"ok": True},
        ]
    )
    client._raise_for_top_level_errors = MagicMock()

    payload = await client._execute_with_retries(_request())

    assert payload == {"ok": True}
    assert client._execute_once.await_count == 2
    assert sleeps == [0.5 * (2**0) + 0.05]


@pytest.mark.asyncio
async def test_rate_limit_gate_sleeps_between_attempts(monkeypatch):
    # Zero retry backoff so the inter-request gate is the sleep under test.
    client = _client(
        aliexpress_rate_limit_interval_seconds=0.2,
        aliexpress_retry_backoff_seconds=0.0,
    )
    sleeps: list[float] = []
    clock = {"now": 100.0}

    class _Loop:
        def time(self) -> float:
            return clock["now"]

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)
        clock["now"] += delay

    monkeypatch.setattr("app.aliexpress.api_client.asyncio.sleep", fake_sleep)
    monkeypatch.setattr(
        "app.aliexpress.api_client.asyncio.get_running_loop",
        lambda: _Loop(),
    )
    monkeypatch.setattr("app.aliexpress.api_client.random.uniform", lambda a, b: 0.0)
    client._execute_once = AsyncMock(
        side_effect=[
            AliExpressAPIError("temporary blip", code=500),
            {"ok": True},
        ]
    )
    client._raise_for_top_level_errors = MagicMock()

    payload = await client._execute_with_retries(_request())

    assert payload == {"ok": True}
    assert client._execute_once.await_count == 2
    # Retry backoff sleep(0), then gate enforces the 0.2s minimum interval.
    assert sleeps == [0.0, 0.2]


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [500, 502, 503, 504])
async def test_5xx_errors_are_retried(monkeypatch, status_code: int):
    client = _client()
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.aliexpress.api_client.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("app.aliexpress.api_client.random.uniform", lambda a, b: 0.0)
    client._execute_once = AsyncMock(
        side_effect=[
            AliExpressAPIError("upstream failure", code=status_code),
            {"ok": True},
        ]
    )
    client._raise_for_top_level_errors = MagicMock()

    payload = await client._execute_with_retries(_request())

    assert payload == {"ok": True}
    assert client._execute_once.await_count == 2
    assert sleeps == [0.5]


@pytest.mark.asyncio
async def test_backoff_applies_exponential_growth_and_jitter(monkeypatch):
    client = _client()
    sleeps: list[float] = []
    jitter_values = iter([0.01, 0.02, 0.03])

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.aliexpress.api_client.asyncio.sleep", fake_sleep)
    monkeypatch.setattr(
        "app.aliexpress.api_client.random.uniform",
        lambda a, b: next(jitter_values),
    )
    client._execute_once = AsyncMock(side_effect=AliExpressAPIError("timeout", code=408))
    client._raise_for_top_level_errors = MagicMock()

    with pytest.raises(AliExpressAPIError):
        await client._execute_with_retries(_request())

    assert sleeps == [
        0.5 * (2**0) + 0.01,
        0.5 * (2**1) + 0.02,
        0.5 * (2**2) + 0.03,
    ]


@pytest.mark.asyncio
async def test_max_attempts_matches_configured_retry_budget(monkeypatch):
    client = _client(aliexpress_max_retries=2)
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.aliexpress.api_client.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("app.aliexpress.api_client.random.uniform", lambda a, b: 0.0)
    client._execute_once = AsyncMock(side_effect=AliExpressAPIError("timeout"))
    client._raise_for_top_level_errors = MagicMock()

    with pytest.raises(AliExpressAPIError):
        await client._execute_with_retries(_request())

    assert client._execute_once.await_count == 3  # max_retries(2) + 1
    assert len(sleeps) == 2


@pytest.mark.asyncio
async def test_credentials_error_raises_immediately_without_retry(monkeypatch):
    client = _client()
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.aliexpress.api_client.asyncio.sleep", fake_sleep)
    error = AliExpressCredentialsError("invalid app key", code=29)
    client._execute_once = AsyncMock(side_effect=error)
    client._raise_for_top_level_errors = MagicMock()

    with pytest.raises(AliExpressCredentialsError) as exc_info:
        await client._execute_with_retries(_request())

    assert exc_info.value is error
    assert client._execute_once.await_count == 1
    assert sleeps == []


def test_is_retryable_classifies_status_codes_and_message_hints():
    client = _client()

    assert client._is_retryable(AliExpressRateLimitError("limited", code=429)) is True
    assert client._is_retryable(AliExpressAPIError("oops", code=408)) is True
    assert client._is_retryable(AliExpressAPIError("oops", code=500)) is True
    assert client._is_retryable(AliExpressAPIError("request timeout")) is True
    assert client._is_retryable(AliExpressAPIError("temporarily unavailable")) is True
    assert client._is_retryable(AliExpressAPIError("bad request", code=400)) is False
    assert client._is_retryable(AliExpressAPIError("not found", code=404)) is False
    assert client._is_retryable(RuntimeError("boom")) is False


def test_backoff_seconds_formula_with_mocked_jitter(monkeypatch):
    client = _client(aliexpress_retry_backoff_seconds=0.5)
    monkeypatch.setattr("app.aliexpress.api_client.random.uniform", lambda a, b: 0.25)

    assert client._backoff_seconds(0) == 0.75
    assert client._backoff_seconds(1) == 1.25
    assert client._backoff_seconds(2) == 2.25
