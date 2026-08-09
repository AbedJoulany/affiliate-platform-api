"""Exception-identity hygiene for AliExpress discovery refresh paths."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.aliexpress.exceptions import AliExpressAPIError as DomainAliExpressAPIError
from app.services.exceptions import AliExpressAPIError as ServiceAliExpressAPIError
from app.services.product_discovery_persistence import ProductDiscoveryPersistenceService
from app.worker.tasks import discovery as discovery_tasks


def _persistence_service(client) -> ProductDiscoveryPersistenceService:
    session = MagicMock()
    return ProductDiscoveryPersistenceService(session=session, client=client)


@pytest.mark.asyncio
async def test_refresh_categories_propagates_domain_aliexpress_api_error():
    client = MagicMock()
    client.get_categories = AsyncMock(
        side_effect=DomainAliExpressAPIError("categories failed", code=503)
    )
    service = _persistence_service(client)

    with pytest.raises(DomainAliExpressAPIError) as exc_info:
        await service.refresh_categories()

    assert type(exc_info.value) is DomainAliExpressAPIError
    assert not isinstance(exc_info.value, ServiceAliExpressAPIError)
    assert exc_info.value.message == "categories failed"
    assert exc_info.value.code == 503


@pytest.mark.asyncio
async def test_refresh_hot_products_propagates_domain_aliexpress_api_error():
    service = _persistence_service(MagicMock())
    service.discovery.discover = AsyncMock(
        side_effect=DomainAliExpressAPIError("hot failed", code=502)
    )

    with pytest.raises(DomainAliExpressAPIError) as exc_info:
        await service.refresh_hot_products()

    assert type(exc_info.value) is DomainAliExpressAPIError
    assert not isinstance(exc_info.value, ServiceAliExpressAPIError)


@pytest.mark.asyncio
async def test_refresh_trending_products_propagates_domain_aliexpress_api_error():
    service = _persistence_service(MagicMock())
    service.discovery.discover = AsyncMock(
        side_effect=DomainAliExpressAPIError("trending failed", code=500)
    )

    with pytest.raises(DomainAliExpressAPIError) as exc_info:
        await service.refresh_trending_products()

    assert type(exc_info.value) is DomainAliExpressAPIError
    assert not isinstance(exc_info.value, ServiceAliExpressAPIError)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("helper_name", "service_method"),
    [
        ("_refresh_hot_products", "refresh_hot_products"),
        ("_refresh_trending_products", "refresh_trending_products"),
        ("_refresh_categories", "refresh_categories"),
    ],
)
async def test_discovery_task_helpers_surface_domain_exception(
    helper_name: str,
    service_method: str,
):
    error = DomainAliExpressAPIError("domain failure", code=503)
    session = MagicMock()
    session.commit = AsyncMock()
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=None)
    session_maker = MagicMock(return_value=session_cm)

    service = MagicMock()
    method = AsyncMock(side_effect=error)
    setattr(service, service_method, method)

    with (
        patch.object(discovery_tasks, "get_async_session_maker", return_value=session_maker),
        patch.object(discovery_tasks, "AliExpressAffiliateClient", return_value=MagicMock()),
        patch.object(
            discovery_tasks,
            "ProductDiscoveryPersistenceService",
            return_value=service,
        ),
    ):
        helper = getattr(discovery_tasks, helper_name)
        with pytest.raises(DomainAliExpressAPIError) as exc_info:
            await helper()

    assert type(exc_info.value) is DomainAliExpressAPIError
    assert not isinstance(exc_info.value, ServiceAliExpressAPIError)
    method.assert_awaited_once()
    session.commit.assert_not_awaited()
