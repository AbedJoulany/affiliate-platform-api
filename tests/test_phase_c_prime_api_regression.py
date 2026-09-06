"""Phase C' Task 4 — Integration / API regression validation.

Boundary-level checks that Tasks 1–3 retry hardening remains transparent to
API contracts and does not introduce nested Celery HTTP retries.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest

from app.ai.gemini_provider import GeminiProvider
from app.ai.openai_provider import OpenAIProvider
from app.aliexpress.client import AliExpressAffiliateClient
from app.aliexpress.exceptions import AliExpressAPIError as DomainAliExpressAPIError
from app.api.deps_aliexpress import get_aliexpress_client
from app.core.config import Settings
from app.core.enums import AIProviderType
from app.main import app as fastapi_app
from app.services.exceptions import AIProviderError
from app.worker.celery_app import celery_app
from app.worker.tasks import discovery as discovery_tasks
from tests.conftest import provision_test_user

API_PREFIX = "/api/v1"
PASSWORD = "StrongP@ssw0rd"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _login_affiliate(client) -> str:
    email = f"cprime-{uuid4().hex[:8]}@example.com"
    await provision_test_user(
        email=email,
        password=PASSWORD,
        full_name="CPrime User",
        role="user",
    )
    login = await client.post(
        f"{API_PREFIX}/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


def _fake_url_fetch(monkeypatch) -> None:
    async def fake_fetch(self, url: str) -> SimpleNamespace:
        return SimpleNamespace(
            url=url,
            title="Example Title",
            description="Example description",
            image_url="https://example.com/image.jpg",
        )

    monkeypatch.setattr("app.services.ai_content.ProductURLFetcher.fetch", fake_fetch)


class _FakeAsyncClient:
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


def _install_httpx_queue(monkeypatch, responses: list[object]) -> None:
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


def _total_httpx_posts() -> int:
    return sum(client.post_calls for client in _FakeAsyncClient.instances)


def _http_status_error(
    status_code: int,
    *,
    text: str = "error",
) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://example.test/v1")
    response = httpx.Response(status_code, request=request, text=text)
    return httpx.HTTPStatusError("error", request=request, response=response)


def _json_response(payload: dict, status_code: int = 200) -> httpx.Response:
    request = httpx.Request("POST", "https://example.test/v1")
    return httpx.Response(status_code, request=request, json=payload)


def _openai_success(text: str = "نص تسويقي") -> dict:
    return {"choices": [{"message": {"content": text}}]}


def _gemini_success(text: str = "نص تسويقي") -> dict:
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def _wire_real_providers(monkeypatch) -> None:
    """Route factory through real provider classes with test credentials."""

    def fake_get_ai_provider(provider: AIProviderType | None = None):
        provider_type = provider or AIProviderType.OPENAI
        if provider_type == AIProviderType.OPENAI:
            return OpenAIProvider(
                api_key="sk-test",
                model="gpt-test",
                base_url="https://openai.test/v1",
            )
        if provider_type == AIProviderType.GEMINI:
            return GeminiProvider(
                api_key="gemini-test",
                model="gemini-test",
                base_url="https://gemini.test/v1beta",
            )
        raise AIProviderError(f"Unsupported provider: {provider_type}")

    monkeypatch.setattr("app.services.ai_content.get_ai_provider", fake_get_ai_provider)
    _fake_url_fetch(monkeypatch)


def _disable_ai_sleep(monkeypatch) -> list[float]:
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.ai.retry.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("app.ai.retry.random.uniform", lambda a, b: 0.0)
    return sleeps


def _disable_aliexpress_sleep(monkeypatch) -> list[float]:
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.aliexpress.api_client.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("app.aliexpress.api_client.random.uniform", lambda a, b: 0.0)
    return sleeps


def _aliexpress_settings(**overrides) -> Settings:
    values = {
        "aliexpress_app_key": "app-key",
        "aliexpress_app_secret": "app-secret",
        "aliexpress_max_retries": 3,
        "aliexpress_retry_backoff_seconds": 0.5,
        "aliexpress_rate_limit_interval_seconds": 0.0,
    }
    values.update(overrides)
    return Settings(**values)


def _hot_payload() -> dict:
    return {
        "aliexpress_affiliate_hotproduct_query_response": {
            "resp_result": {
                "resp_code": 200,
                "result": {
                    "products": [],
                    "current_page_no": 1,
                    "total_page_no": 1,
                    "current_record_count": 0,
                    "total_record_count": 0,
                    "is_finished": True,
                },
            }
        }
    }


def _trending_payload() -> dict:
    return {
        "aliexpress_affiliate_product_smartmatch_response": {
            "resp_result": {
                "resp_code": 200,
                "result": {
                    "products": [],
                    "current_page_no": 1,
                    "total_page_no": 1,
                    "current_record_count": 0,
                    "total_record_count": 0,
                    "is_finished": True,
                },
            }
        }
    }


# ---------------------------------------------------------------------------
# A/B — AI API + provider selection regression
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider", "payload"),
    [
        ("openai", _openai_success("openai-ok")),
        ("gemini", _gemini_success("gemini-ok")),
    ],
)
async def test_ai_generate_success_preserves_contract(client, monkeypatch, provider, payload):
    _wire_real_providers(monkeypatch)
    _install_httpx_queue(monkeypatch, [_json_response(payload)])
    send_task = MagicMock()
    monkeypatch.setattr(celery_app, "send_task", send_task)

    token = await _login_affiliate(client)
    response = await client.post(
        f"{API_PREFIX}/ai-content/generate",
        headers=auth_headers(token),
        json={"url": "https://example.com/item", "provider": provider},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == provider
    assert body["source_url"] == "https://example.com/item"
    assert body["content"] == f"{provider}-ok"
    assert "content_type" in body
    assert "tone" in body
    assert "language" in body
    assert "length" in body
    assert _total_httpx_posts() == 1
    send_task.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["openai", "gemini"])
@pytest.mark.parametrize(
    "failure",
    [
        httpx.ConnectError("down"),
        _http_status_error(429, text="rate limited"),
        _http_status_error(503, text="upstream"),
    ],
    ids=["network", "429", "5xx"],
)
async def test_ai_generate_retry_exhaustion_preserves_error_contract(
    client,
    monkeypatch,
    provider: str,
    failure: Exception,
):
    _wire_real_providers(monkeypatch)
    _disable_ai_sleep(monkeypatch)
    _install_httpx_queue(monkeypatch, [failure, failure])
    send_task = MagicMock()
    monkeypatch.setattr(celery_app, "send_task", send_task)

    token = await _login_affiliate(client)
    response = await client.post(
        f"{API_PREFIX}/ai-content/generate",
        headers=auth_headers(token),
        json={"url": "https://example.com/item", "provider": provider},
    )

    assert response.status_code == 502
    assert isinstance(response.json()["detail"], str)
    assert response.json()["detail"]
    assert _total_httpx_posts() == 2
    send_task.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["openai", "gemini"])
@pytest.mark.parametrize("status_code", [400, 401, 403, 404])
async def test_ai_generate_non_retryable_preserves_error_contract(
    client,
    monkeypatch,
    provider: str,
    status_code: int,
):
    _wire_real_providers(monkeypatch)
    sleeps = _disable_ai_sleep(monkeypatch)
    _install_httpx_queue(
        monkeypatch,
        [_http_status_error(status_code, text=f"permanent-{status_code}")],
    )

    token = await _login_affiliate(client)
    response = await client.post(
        f"{API_PREFIX}/ai-content/generate",
        headers=auth_headers(token),
        json={"url": "https://example.com/item", "provider": provider},
    )

    assert response.status_code == 502
    assert f"permanent-{status_code}" in response.json()["detail"]
    assert _total_httpx_posts() == 1
    assert sleeps == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider", "bad_payload", "detail_fragment"),
    [
        ("openai", {"choices": []}, "unexpected response format"),
        ("gemini", {"candidates": []}, "unexpected response format"),
    ],
)
async def test_ai_generate_malformed_response_no_retry(
    client,
    monkeypatch,
    provider: str,
    bad_payload: dict,
    detail_fragment: str,
):
    _wire_real_providers(monkeypatch)
    sleeps = _disable_ai_sleep(monkeypatch)
    _install_httpx_queue(monkeypatch, [_json_response(bad_payload)])

    token = await _login_affiliate(client)
    response = await client.post(
        f"{API_PREFIX}/ai-content/generate",
        headers=auth_headers(token),
        json={"url": "https://example.com/item", "provider": provider},
    )

    assert response.status_code == 502
    assert detail_fragment in response.json()["detail"]
    assert _total_httpx_posts() == 1
    assert sleeps == []


@pytest.mark.asyncio
async def test_ai_provider_selection_is_exact_and_not_celery(client, monkeypatch):
    created: list[str] = []

    def fake_get_ai_provider(provider: AIProviderType | None = None):
        provider_type = provider or AIProviderType.OPENAI
        created.append(provider_type.value)

        class _Provider:
            name = provider_type.value

            @property
            def is_configured(self) -> bool:
                return True

            async def generate_content(self, prompt: str) -> str:
                return f"from-{self.name}"

        return _Provider()

    monkeypatch.setattr("app.services.ai_content.get_ai_provider", fake_get_ai_provider)
    _fake_url_fetch(monkeypatch)
    send_task = MagicMock()
    delay = MagicMock()
    monkeypatch.setattr(celery_app, "send_task", send_task)
    for task in (
        discovery_tasks.refresh_hot_products,
        discovery_tasks.refresh_trending_products,
        discovery_tasks.refresh_categories,
    ):
        monkeypatch.setattr(task, "delay", delay)
        monkeypatch.setattr(task, "apply_async", delay)

    token = await _login_affiliate(client)

    openai_resp = await client.post(
        f"{API_PREFIX}/ai-content/generate",
        headers=auth_headers(token),
        json={"url": "https://example.com/a", "provider": "openai"},
    )
    gemini_resp = await client.post(
        f"{API_PREFIX}/ai-content/generate",
        headers=auth_headers(token),
        json={"url": "https://example.com/b", "provider": "gemini"},
    )

    assert openai_resp.status_code == 200
    assert openai_resp.json()["provider"] == "openai"
    assert openai_resp.json()["content"] == "from-openai"
    assert gemini_resp.status_code == 200
    assert gemini_resp.json()["provider"] == "gemini"
    assert gemini_resp.json()["content"] == "from-gemini"
    assert created == ["openai", "gemini"]
    send_task.assert_not_called()
    delay.assert_not_called()


# ---------------------------------------------------------------------------
# C — Discovery API regression
# ---------------------------------------------------------------------------


@pytest.fixture
def aliexpress_client_override():
    """Install/clear FastAPI dependency override for AliExpress client."""
    created: dict[str, AliExpressAffiliateClient] = {}

    def install(client: AliExpressAffiliateClient) -> AliExpressAffiliateClient:
        created["client"] = client
        fastapi_app.dependency_overrides[get_aliexpress_client] = lambda: client
        return client

    yield install
    fastapi_app.dependency_overrides.pop(get_aliexpress_client, None)


@pytest.mark.asyncio
async def test_discover_hot_success_preserves_contract(
    client,
    monkeypatch,
    aliexpress_client_override,
):
    settings = _aliexpress_settings()
    ae_client = AliExpressAffiliateClient(settings)
    ae_client._execute_once = AsyncMock(return_value=_hot_payload())
    ae_client._raise_for_top_level_errors = MagicMock()
    aliexpress_client_override(ae_client)

    response = await client.get(f"{API_PREFIX}/products/discover/hot")

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "hot"
    assert body["items"] == []
    assert "page" in body
    assert "total_pages" in body
    assert "sort" in body
    assert ae_client._execute_once.await_count == 1


@pytest.mark.asyncio
async def test_discover_trending_success_preserves_contract(
    client,
    monkeypatch,
    aliexpress_client_override,
):
    settings = _aliexpress_settings()
    ae_client = AliExpressAffiliateClient(settings)
    ae_client._execute_once = AsyncMock(return_value=_trending_payload())
    ae_client._raise_for_top_level_errors = MagicMock()
    aliexpress_client_override(ae_client)

    response = await client.get(f"{API_PREFIX}/products/discover/trending")

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "trending"
    assert isinstance(body["items"], list)
    assert ae_client._execute_once.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "/products/discover/hot",
        "/products/discover/trending",
    ],
)
async def test_discover_retry_exhaustion_preserves_api_error(
    client,
    monkeypatch,
    aliexpress_client_override,
    path: str,
):
    settings = _aliexpress_settings()
    expected_attempts = settings.aliexpress_max_retries + 1
    sleeps = _disable_aliexpress_sleep(monkeypatch)
    ae_client = AliExpressAffiliateClient(settings)
    ae_client._execute_once = AsyncMock(
        side_effect=DomainAliExpressAPIError("aliexpress exhausted", code=503)
    )
    aliexpress_client_override(ae_client)

    # Discovery API path must not touch Celery.
    send_task = MagicMock()
    monkeypatch.setattr(celery_app, "send_task", send_task)

    response = await client.get(f"{API_PREFIX}{path}")

    assert response.status_code == 502
    assert response.json()["detail"] == "aliexpress exhausted"
    assert ae_client._execute_once.await_count == expected_attempts
    assert len(sleeps) == settings.aliexpress_max_retries
    send_task.assert_not_called()


@pytest.mark.asyncio
async def test_discover_non_retryable_preserves_single_attempt(
    client,
    monkeypatch,
    aliexpress_client_override,
):
    settings = _aliexpress_settings()
    sleeps = _disable_aliexpress_sleep(monkeypatch)
    ae_client = AliExpressAffiliateClient(settings)
    ae_client._execute_once = AsyncMock(
        side_effect=DomainAliExpressAPIError("bad request", code=400)
    )
    aliexpress_client_override(ae_client)

    response = await client.get(f"{API_PREFIX}/products/discover/hot")

    assert response.status_code == 502
    assert response.json()["detail"] == "bad request"
    assert ae_client._execute_once.await_count == 1
    assert sleeps == []


# ---------------------------------------------------------------------------
# D — Celery discovery boundary (thin integration; Task 3 owns deep coverage)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "task",
    [
        discovery_tasks.refresh_hot_products,
        discovery_tasks.refresh_trending_products,
        discovery_tasks.refresh_categories,
    ],
    ids=lambda t: t.name.rsplit(".", 1)[-1],
)
def test_discovery_celery_tasks_still_have_no_http_autoretry(task):
    autoretry_for = getattr(task, "autoretry_for", ()) or ()
    assert DomainAliExpressAPIError not in autoretry_for
    assert AIProviderError not in autoretry_for
    assert not getattr(task, "retry_backoff", False)


@pytest.mark.asyncio
async def test_discovery_task_single_invocation_with_client_budget(monkeypatch):
    """One Celery helper entry; HTTP attempts stay within the client budget."""
    settings = _aliexpress_settings()
    expected = settings.aliexpress_max_retries + 1
    _disable_aliexpress_sleep(monkeypatch)

    ae_client = AliExpressAffiliateClient(settings)
    ae_client._execute_once = AsyncMock(
        side_effect=DomainAliExpressAPIError("still down", code=502)
    )

    session = MagicMock()
    session.commit = AsyncMock()
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=None)
    session_maker = MagicMock(return_value=session_cm)

    from app.services.product_discovery_persistence import ProductDiscoveryPersistenceService

    service = ProductDiscoveryPersistenceService(session, ae_client)
    entries = {"n": 0}
    original = discovery_tasks._refresh_hot_products

    async def counting() -> dict:
        entries["n"] += 1
        return await original()

    monkeypatch.setattr(discovery_tasks, "_refresh_hot_products", counting)

    with (
        patch.object(discovery_tasks, "get_async_session_maker", return_value=session_maker),
        patch.object(discovery_tasks, "AliExpressAffiliateClient", return_value=ae_client),
        patch.object(
            discovery_tasks,
            "ProductDiscoveryPersistenceService",
            return_value=service,
        ),
    ):
        with pytest.raises(DomainAliExpressAPIError):
            await discovery_tasks._refresh_hot_products()

    assert entries["n"] == 1
    assert ae_client._execute_once.await_count == expected
