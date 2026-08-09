"""Phase C' Task 2 — AI provider retry hardening coverage."""

from __future__ import annotations

import httpx
import pytest

from app.ai.gemini_provider import GeminiProvider
from app.ai.openai_provider import OpenAIProvider
from app.ai.retry import (
    AI_BASE_BACKOFF_SECONDS,
    AI_JITTER_SECONDS,
    AI_MAX_ATTEMPTS,
    classify_httpx_failure,
    compute_backoff_seconds,
    execute_with_retries,
    parse_retry_after,
)
from app.services.exceptions import AIProviderError


def _http_status_error(
    status_code: int,
    *,
    text: str = "error",
    headers: dict[str, str] | None = None,
) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://example.test/v1")
    response = httpx.Response(
        status_code,
        request=request,
        text=text,
        headers=headers or {},
    )
    return httpx.HTTPStatusError("error", request=request, response=response)


# ---------------------------------------------------------------------------
# Classifier / backoff unit tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("exc", "retryable"),
    [
        (httpx.ConnectError("refused"), True),
        (httpx.ReadTimeout("timed out"), True),
        (httpx.ConnectTimeout("connect timed out"), True),
        (_http_status_error(429), True),
        (_http_status_error(500), True),
        (_http_status_error(502), True),
        (_http_status_error(503), True),
        (_http_status_error(504), True),
        (_http_status_error(599), True),
        (_http_status_error(400), False),
        (_http_status_error(401), False),
        (_http_status_error(403), False),
        (_http_status_error(404), False),
        (RuntimeError("unexpected"), False),
        (ValueError("bad config"), False),
    ],
)
def test_classify_httpx_failure_matrix(exc: BaseException, retryable: bool):
    assert classify_httpx_failure(exc).retryable is retryable


def test_parse_retry_after_valid_and_invalid():
    request = httpx.Request("POST", "https://example.test/v1")
    ok = httpx.Response(429, request=request, headers={"Retry-After": "7"})
    assert parse_retry_after(ok) == 7.0

    missing = httpx.Response(429, request=request)
    assert parse_retry_after(missing) is None

    malformed = httpx.Response(429, request=request, headers={"Retry-After": "soon"})
    assert parse_retry_after(malformed) is None

    negative = httpx.Response(429, request=request, headers={"Retry-After": "-1"})
    assert parse_retry_after(negative) is None

    capped = httpx.Response(429, request=request, headers={"Retry-After": "999"})
    assert parse_retry_after(capped) == 60.0


def test_compute_backoff_uses_base_and_jitter(monkeypatch):
    monkeypatch.setattr("app.ai.retry.random.uniform", lambda a, b: 0.25)
    delay = compute_backoff_seconds(0)
    assert delay == AI_BASE_BACKOFF_SECONDS + 0.25
    assert 0 < delay <= AI_BASE_BACKOFF_SECONDS + AI_JITTER_SECONDS


def test_compute_backoff_prefers_retry_after(monkeypatch):
    monkeypatch.setattr("app.ai.retry.random.uniform", lambda a, b: 0.0)
    delay = compute_backoff_seconds(0, retry_after=7.0)
    assert delay == 7.0


@pytest.mark.asyncio
async def test_execute_with_retries_respects_max_attempts(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.ai.retry.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("app.ai.retry.random.uniform", lambda a, b: 0.0)

    calls = {"n": 0}

    async def always_fail():
        calls["n"] += 1
        raise httpx.ConnectError("down")

    with pytest.raises(httpx.ConnectError):
        await execute_with_retries(always_fail, provider="test")

    assert calls["n"] == AI_MAX_ATTEMPTS
    assert sleeps == [AI_BASE_BACKOFF_SECONDS]


# ---------------------------------------------------------------------------
# Provider integration helpers
# ---------------------------------------------------------------------------


class _FakeAsyncClient:
    """Minimal AsyncClient stand-in that records POST calls."""

    instances: list[_FakeAsyncClient] = []

    def __init__(self, *args, **kwargs) -> None:
        self.post_calls = 0
        _FakeAsyncClient.instances.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def post(self, *args, **kwargs):
        raise NotImplementedError


def _install_post_queue(monkeypatch, responses: list[object]):
    queue = list(responses)
    _FakeAsyncClient.instances = []

    async def fake_post(self, *args, **kwargs):
        self.post_calls += 1
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    _FakeAsyncClient.post = fake_post  # type: ignore[method-assign]
    monkeypatch.setattr("httpx.AsyncClient", _FakeAsyncClient)
    return queue


def _json_response(payload: dict, status_code: int = 200) -> httpx.Response:
    request = httpx.Request("POST", "https://example.test/v1")
    return httpx.Response(status_code, request=request, json=payload)


def _openai_success_payload(text: str = "generated") -> dict:
    return {"choices": [{"message": {"content": text}}]}


def _gemini_success_payload(text: str = "generated") -> dict:
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def _openai_provider() -> OpenAIProvider:
    return OpenAIProvider(
        api_key="sk-test",
        model="gpt-test",
        base_url="https://openai.test/v1",
    )


def _gemini_provider() -> GeminiProvider:
    return GeminiProvider(
        api_key="gemini-test-key",
        model="gemini-test",
        base_url="https://gemini.test/v1beta",
    )


def _total_posts() -> int:
    return sum(client.post_calls for client in _FakeAsyncClient.instances)


# ---------------------------------------------------------------------------
# OpenAI provider behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_openai_success_single_attempt(monkeypatch):
    _install_post_queue(monkeypatch, [_json_response(_openai_success_payload("ok"))])
    result = await _openai_provider().generate_content("prompt")
    assert result == "ok"
    assert _total_posts() == 1


@pytest.mark.asyncio
async def test_openai_network_failure_then_success(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.ai.retry.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("app.ai.retry.random.uniform", lambda a, b: 0.0)
    _install_post_queue(
        monkeypatch,
        [
            httpx.ConnectError("reset"),
            _json_response(_openai_success_payload("recovered")),
        ],
    )

    result = await _openai_provider().generate_content("prompt")
    assert result == "recovered"
    assert _total_posts() == 2
    assert sleeps == [AI_BASE_BACKOFF_SECONDS]


@pytest.mark.asyncio
async def test_openai_429_then_success(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.ai.retry.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("app.ai.retry.random.uniform", lambda a, b: 0.0)
    _install_post_queue(
        monkeypatch,
        [
            _http_status_error(429, text="rate limited"),
            _json_response(_openai_success_payload("ok")),
        ],
    )

    result = await _openai_provider().generate_content("prompt")
    assert result == "ok"
    assert _total_posts() == 2
    assert sleeps == [AI_BASE_BACKOFF_SECONDS]


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [500, 502, 503, 504])
async def test_openai_5xx_then_success(monkeypatch, status_code: int):
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.ai.retry.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("app.ai.retry.random.uniform", lambda a, b: 0.0)
    _install_post_queue(
        monkeypatch,
        [
            _http_status_error(status_code, text="upstream"),
            _json_response(_openai_success_payload("ok")),
        ],
    )

    result = await _openai_provider().generate_content("prompt")
    assert result == "ok"
    assert _total_posts() == 2


@pytest.mark.asyncio
async def test_openai_retry_exhaustion_raises_ai_provider_error(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.ai.retry.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("app.ai.retry.random.uniform", lambda a, b: 0.0)
    _install_post_queue(
        monkeypatch,
        [
            _http_status_error(503, text="still down"),
            _http_status_error(503, text="still down"),
        ],
    )

    with pytest.raises(AIProviderError, match="still down"):
        await _openai_provider().generate_content("prompt")

    assert _total_posts() == 2
    assert len(sleeps) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [400, 401, 403, 404])
async def test_openai_non_retryable_status(monkeypatch, status_code: int):
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.ai.retry.asyncio.sleep", fake_sleep)
    _install_post_queue(monkeypatch, [_http_status_error(status_code, text="nope")])

    with pytest.raises(AIProviderError, match="nope"):
        await _openai_provider().generate_content("prompt")

    assert _total_posts() == 1
    assert sleeps == []


@pytest.mark.asyncio
async def test_openai_malformed_response_no_retry(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.ai.retry.asyncio.sleep", fake_sleep)
    _install_post_queue(monkeypatch, [_json_response({"choices": []})])

    with pytest.raises(AIProviderError, match="unexpected response format"):
        await _openai_provider().generate_content("prompt")

    assert _total_posts() == 1
    assert sleeps == []


@pytest.mark.asyncio
async def test_openai_429_honors_retry_after(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.ai.retry.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("app.ai.retry.random.uniform", lambda a, b: 0.0)
    _install_post_queue(
        monkeypatch,
        [
            _http_status_error(429, text="slow down", headers={"Retry-After": "7"}),
            _json_response(_openai_success_payload("ok")),
        ],
    )

    result = await _openai_provider().generate_content("prompt")
    assert result == "ok"
    assert _total_posts() == 2
    assert sleeps == [7.0]


# ---------------------------------------------------------------------------
# Gemini provider behavior
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gemini_success_single_attempt(monkeypatch):
    _install_post_queue(monkeypatch, [_json_response(_gemini_success_payload("ok"))])
    result = await _gemini_provider().generate_content("prompt")
    assert result == "ok"
    assert _total_posts() == 1


@pytest.mark.asyncio
async def test_gemini_network_failure_then_success(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.ai.retry.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("app.ai.retry.random.uniform", lambda a, b: 0.0)
    _install_post_queue(
        monkeypatch,
        [
            httpx.ReadTimeout("timeout"),
            _json_response(_gemini_success_payload("recovered")),
        ],
    )

    result = await _gemini_provider().generate_content("prompt")
    assert result == "recovered"
    assert _total_posts() == 2
    assert sleeps == [AI_BASE_BACKOFF_SECONDS]


@pytest.mark.asyncio
async def test_gemini_429_then_success(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.ai.retry.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("app.ai.retry.random.uniform", lambda a, b: 0.0)
    _install_post_queue(
        monkeypatch,
        [
            _http_status_error(429, text="quota"),
            _json_response(_gemini_success_payload("ok")),
        ],
    )

    result = await _gemini_provider().generate_content("prompt")
    assert result == "ok"
    assert _total_posts() == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [500, 502, 503, 504])
async def test_gemini_5xx_then_success(monkeypatch, status_code: int):
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.ai.retry.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("app.ai.retry.random.uniform", lambda a, b: 0.0)
    _install_post_queue(
        monkeypatch,
        [
            _http_status_error(status_code, text="upstream"),
            _json_response(_gemini_success_payload("ok")),
        ],
    )

    result = await _gemini_provider().generate_content("prompt")
    assert result == "ok"
    assert _total_posts() == 2


@pytest.mark.asyncio
async def test_gemini_retry_exhaustion_raises_ai_provider_error(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.ai.retry.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("app.ai.retry.random.uniform", lambda a, b: 0.0)
    _install_post_queue(
        monkeypatch,
        [
            httpx.ConnectError("down"),
            httpx.ConnectError("down"),
        ],
    )

    with pytest.raises(AIProviderError, match="down"):
        await _gemini_provider().generate_content("prompt")

    assert _total_posts() == 2
    assert len(sleeps) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [400, 401, 403, 404])
async def test_gemini_non_retryable_status(monkeypatch, status_code: int):
    """Gemini auth commonly surfaces as 403; 401 is also treated as permanent."""
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.ai.retry.asyncio.sleep", fake_sleep)
    _install_post_queue(monkeypatch, [_http_status_error(status_code, text="denied")])

    with pytest.raises(AIProviderError, match="denied"):
        await _gemini_provider().generate_content("prompt")

    assert _total_posts() == 1
    assert sleeps == []


@pytest.mark.asyncio
async def test_gemini_malformed_response_no_retry(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.ai.retry.asyncio.sleep", fake_sleep)
    _install_post_queue(monkeypatch, [_json_response({"candidates": []})])

    with pytest.raises(AIProviderError, match="unexpected response format"):
        await _gemini_provider().generate_content("prompt")

    assert _total_posts() == 1
    assert sleeps == []


@pytest.mark.asyncio
async def test_gemini_429_honors_retry_after(monkeypatch):
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.ai.retry.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("app.ai.retry.random.uniform", lambda a, b: 0.0)
    _install_post_queue(
        monkeypatch,
        [
            _http_status_error(429, text="quota", headers={"Retry-After": "5"}),
            _json_response(_gemini_success_payload("ok")),
        ],
    )

    result = await _gemini_provider().generate_content("prompt")
    assert result == "ok"
    assert _total_posts() == 2
    assert sleeps == [5.0]


@pytest.mark.asyncio
async def test_unconfigured_provider_does_not_call_http(monkeypatch):
    _FakeAsyncClient.instances = []
    monkeypatch.setattr("httpx.AsyncClient", _FakeAsyncClient)

    openai = _openai_provider()
    openai.api_key = None
    gemini = _gemini_provider()
    gemini.api_key = None

    with pytest.raises(AIProviderError, match="not configured"):
        await openai.generate_content("prompt")
    with pytest.raises(AIProviderError, match="not configured"):
        await gemini.generate_content("prompt")

    assert _FakeAsyncClient.instances == []
