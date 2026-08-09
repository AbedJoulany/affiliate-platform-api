"""Phase C' Task 3 — AliExpress no-nested-retry regression protection.

Guards the Task 0 ownership rule:

    AliExpress HTTP retries live only in api_client._execute_with_retries.
    Discovery Celery tasks must not autoretry the same HTTP exceptions.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.aliexpress.client import AliExpressAffiliateClient
from app.aliexpress.exceptions import (
    AliExpressAPIError as DomainAliExpressAPIError,
)
from app.aliexpress.exceptions import (
    AliExpressRateLimitError,
)
from app.core.config import Settings
from app.services.exceptions import AliExpressAPIError as ServiceAliExpressAPIError
from app.services.product_discovery_persistence import ProductDiscoveryPersistenceService
from app.worker.tasks import discovery as discovery_tasks
from app.worker.tasks import publishing as publishing_tasks

DISCOVERY_TASKS = (
    discovery_tasks.refresh_hot_products,
    discovery_tasks.refresh_trending_products,
    discovery_tasks.refresh_categories,
)

_ALIEXPRESS_HTTP_EXCEPTIONS = (
    DomainAliExpressAPIError,
    AliExpressRateLimitError,
    ServiceAliExpressAPIError,
)


def _client_settings(**overrides) -> Settings:
    values = {
        "aliexpress_app_key": "app-key",
        "aliexpress_app_secret": "app-secret",
        "aliexpress_max_retries": 3,
        "aliexpress_retry_backoff_seconds": 0.5,
        "aliexpress_rate_limit_interval_seconds": 0.0,
        "aliexpress_discovery_refresh_batch_size": 10,
    }
    values.update(overrides)
    return Settings(**values)


def _expected_client_attempts(settings: Settings) -> int:
    return settings.aliexpress_max_retries + 1


@contextmanager
def _discovery_runtime(client: AliExpressAffiliateClient):
    """Patch discovery task deps so helpers use the provided client once."""
    session = MagicMock()
    session.commit = AsyncMock()
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=None)
    session_maker = MagicMock(return_value=session_cm)

    service = ProductDiscoveryPersistenceService(session, client)
    service.category_repo = MagicMock()
    service.category_repo.replace_all = AsyncMock(return_value=1)

    with (
        patch.object(discovery_tasks, "get_async_session_maker", return_value=session_maker),
        patch.object(discovery_tasks, "AliExpressAffiliateClient", return_value=client),
        patch.object(
            discovery_tasks,
            "ProductDiscoveryPersistenceService",
            return_value=service,
        ),
    ):
        yield session, service


def _disable_real_sleeps(monkeypatch) -> list[float]:
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.aliexpress.api_client.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("app.aliexpress.api_client.random.uniform", lambda a, b: 0.0)
    return sleeps


def _category_payload() -> dict:
    return {
        "aliexpress_affiliate_category_get_response": {
            "resp_result": {
                "resp_code": 200,
                "result": {
                    "categories": [
                        {
                            "category_id": 1,
                            "category_name": "Electronics",
                            "parent_category_id": 0,
                        }
                    ]
                },
            }
        }
    }


def _hot_products_payload() -> dict:
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


# ---------------------------------------------------------------------------
# Celery configuration: no AliExpress HTTP autoretry on discovery tasks
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("task", DISCOVERY_TASKS, ids=lambda t: t.name.rsplit(".", 1)[-1])
def test_discovery_tasks_have_no_aliexpress_http_autoretry(task):
    autoretry_for = getattr(task, "autoretry_for", ()) or ()
    assert autoretry_for == ()
    for exc_type in _ALIEXPRESS_HTTP_EXCEPTIONS:
        assert exc_type not in autoretry_for

    # Celery's default max_retries is unrelated; only HTTP autoretry must stay off.
    assert not getattr(task, "retry_backoff", False)
    assert getattr(task, "retry_kwargs", None) in (None, {})


def test_publishing_tasks_do_not_autoretry_aliexpress_http_errors():
    for task in (
        publishing_tasks.process_publish_queue,
        publishing_tasks.publish_queue_item_task,
    ):
        assert DomainAliExpressAPIError not in task.autoretry_for
        assert ServiceAliExpressAPIError not in task.autoretry_for
        assert AliExpressRateLimitError not in task.autoretry_for


# ---------------------------------------------------------------------------
# Single Celery execution — failure does not re-enter the task body
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "task_name",
    [
        "refresh_hot_products",
        "refresh_trending_products",
        "refresh_categories",
    ],
)
def test_discovery_celery_task_runs_helper_once_on_domain_failure(monkeypatch, task_name: str):
    calls = {"n": 0}

    async def failing_helper() -> dict:
        calls["n"] += 1
        raise DomainAliExpressAPIError("client exhausted", code=503)

    monkeypatch.setattr(discovery_tasks, f"_{task_name}", failing_helper)

    task = getattr(discovery_tasks, task_name)
    with pytest.raises(DomainAliExpressAPIError) as exc_info:
        task()

    assert type(exc_info.value) is DomainAliExpressAPIError
    assert not isinstance(exc_info.value, ServiceAliExpressAPIError)
    assert calls["n"] == 1


# ---------------------------------------------------------------------------
# Client attempt budget through discovery path (no multiplication)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_categories_exhaustion_uses_client_budget_only(monkeypatch):
    settings = _client_settings()
    client = AliExpressAffiliateClient(settings)
    expected = _expected_client_attempts(settings)
    sleeps = _disable_real_sleeps(monkeypatch)
    client._execute_once = AsyncMock(
        side_effect=DomainAliExpressAPIError("still failing", code=503)
    )

    with _discovery_runtime(client) as (session, _service):
        with pytest.raises(DomainAliExpressAPIError) as exc_info:
            await discovery_tasks._refresh_categories()

    assert type(exc_info.value) is DomainAliExpressAPIError
    assert not isinstance(exc_info.value, ServiceAliExpressAPIError)
    assert client._execute_once.await_count == expected
    assert len(sleeps) == settings.aliexpress_max_retries
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_hot_products_exhaustion_uses_client_budget_only(monkeypatch):
    settings = _client_settings()
    client = AliExpressAffiliateClient(settings)
    expected = _expected_client_attempts(settings)
    _disable_real_sleeps(monkeypatch)
    client._execute_once = AsyncMock(
        side_effect=DomainAliExpressAPIError("hot unavailable", code=502)
    )

    with _discovery_runtime(client):
        with pytest.raises(DomainAliExpressAPIError):
            await discovery_tasks._refresh_hot_products()

    assert client._execute_once.await_count == expected


@pytest.mark.asyncio
async def test_trending_products_exhaustion_uses_client_budget_only(monkeypatch):
    settings = _client_settings()
    client = AliExpressAffiliateClient(settings)
    expected = _expected_client_attempts(settings)
    _disable_real_sleeps(monkeypatch)
    client._execute_once = AsyncMock(
        side_effect=AliExpressRateLimitError("rate limited", code=429)
    )

    with _discovery_runtime(client):
        with pytest.raises(AliExpressRateLimitError):
            await discovery_tasks._refresh_trending_products()

    assert client._execute_once.await_count == expected


# ---------------------------------------------------------------------------
# Success / retry-then-success / non-retryable through discovery path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_categories_success_is_single_client_attempt(monkeypatch):
    settings = _client_settings()
    client = AliExpressAffiliateClient(settings)
    sleeps = _disable_real_sleeps(monkeypatch)
    client._execute_once = AsyncMock(return_value=_category_payload())
    client._raise_for_top_level_errors = MagicMock()

    with _discovery_runtime(client) as (session, _service):
        result = await discovery_tasks._refresh_categories()

    assert result == {"synced_categories": 1}
    assert client._execute_once.await_count == 1
    assert sleeps == []
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_categories_retry_then_success_is_client_only(monkeypatch):
    settings = _client_settings()
    client = AliExpressAffiliateClient(settings)
    sleeps = _disable_real_sleeps(monkeypatch)
    client._execute_once = AsyncMock(
        side_effect=[
            DomainAliExpressAPIError("transient", code=503),
            _category_payload(),
        ]
    )
    client._raise_for_top_level_errors = MagicMock()

    with _discovery_runtime(client) as (session, _service):
        result = await discovery_tasks._refresh_categories()

    assert result == {"synced_categories": 1}
    assert client._execute_once.await_count == 2
    assert len(sleeps) == 1
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_categories_non_retryable_is_single_attempt(monkeypatch):
    settings = _client_settings()
    client = AliExpressAffiliateClient(settings)
    sleeps = _disable_real_sleeps(monkeypatch)
    client._execute_once = AsyncMock(
        side_effect=DomainAliExpressAPIError("bad request", code=400)
    )

    with _discovery_runtime(client) as (session, _service):
        with pytest.raises(DomainAliExpressAPIError) as exc_info:
            await discovery_tasks._refresh_categories()

    assert type(exc_info.value) is DomainAliExpressAPIError
    assert client._execute_once.await_count == 1
    assert sleeps == []
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_hot_products_retry_then_success_does_not_reenter_helper(monkeypatch):
    settings = _client_settings()
    client = AliExpressAffiliateClient(settings)
    sleeps = _disable_real_sleeps(monkeypatch)
    helper_entries = {"n": 0}

    client._execute_once = AsyncMock(
        side_effect=[
            DomainAliExpressAPIError("blip", code=500),
            _hot_products_payload(),
        ]
    )
    client._raise_for_top_level_errors = MagicMock()

    original = discovery_tasks._refresh_hot_products

    async def counting_helper() -> dict:
        helper_entries["n"] += 1
        return await original()

    monkeypatch.setattr(discovery_tasks, "_refresh_hot_products", counting_helper)

    with _discovery_runtime(client):
        result = await discovery_tasks._refresh_hot_products()

    assert helper_entries["n"] == 1
    assert client._execute_once.await_count == 2
    assert len(sleeps) == 1
    assert result["mode"] == "hot"
    assert result["discovered"] == 0
