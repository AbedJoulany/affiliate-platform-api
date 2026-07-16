"""Integration tests for all AliExpress HTTP endpoints.

Every endpoint must route through the official IOP SDK (iop.IopClient.execute),
not httpx or manual signing.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from uuid import uuid4

import iop
import pytest
from unittest.mock import MagicMock

from app.aliexpress import api_client as aliexpress_api_client_module
from app.aliexpress.constants import (
    METHOD_DS_IMAGE_SEARCH,
    METHOD_FEATURED_PROMO_PRODUCTS,
    METHOD_HOT_PRODUCT_QUERY,
    METHOD_PRODUCT_DETAIL,
    METHOD_PRODUCT_QUERY,
    METHOD_SMART_MATCH,
)
from app.core.config import get_settings

API_PREFIX = "/api/v1"
PASSWORD = "StrongP@ssw0rd"

SAMPLE_PRODUCT = {
    "product_id": 1234567890,
    "product_title": "Wireless Earbuds",
    "product_main_image_url": "https://example.com/main.jpg",
    "target_sale_price": "29.99",
    "target_original_price": "49.99",
    "target_sale_price_currency": "USD",
    "discount": "40%",
    "evaluate_rate": "96.0%",
    "lastest_volume": 1500,
    "review_number": 120,
    "promotion_link": "https://s.click.aliexpress.com/e/_abc123",
    "product_detail_url": "https://www.aliexpress.com/item/1234567890.html",
}


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def register_admin(client) -> str:
    email = f"admin-{uuid4().hex[:8]}@example.com"
    response = await client.post(
        f"{API_PREFIX}/auth/register",
        json={
            "email": email,
            "password": PASSWORD,
            "full_name": "Admin User",
            "role": "admin",
        },
    )
    assert response.status_code == 201
    login_resp = await client.post(
        f"{API_PREFIX}/auth/login",
        data={"username": email, "password": PASSWORD},
    )
    assert login_resp.status_code == 200
    return login_resp.json()["access_token"]


def _empty_products_response(response_key: str) -> dict:
    return {
        response_key: {
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


def _products_response(response_key: str, products: list[dict] | None = None) -> dict:
    payload = _empty_products_response(response_key)
    payload[response_key]["resp_result"]["result"]["products"] = products or [SAMPLE_PRODUCT.copy()]
    payload[response_key]["resp_result"]["result"]["current_record_count"] = len(
        payload[response_key]["resp_result"]["result"]["products"]
    )
    payload[response_key]["resp_result"]["result"]["total_record_count"] = len(
        payload[response_key]["resp_result"]["result"]["products"]
    )
    return payload


def _product_detail_response() -> dict:
    return _products_response("aliexpress_affiliate_productdetail_get_response")


RESPONSE_BY_METHOD = {
    METHOD_PRODUCT_DETAIL: _product_detail_response,
    METHOD_PRODUCT_QUERY: lambda: _products_response("aliexpress_affiliate_product_query_response"),
    METHOD_HOT_PRODUCT_QUERY: lambda: _products_response("aliexpress_affiliate_hotproduct_query_response"),
    METHOD_SMART_MATCH: lambda: _products_response("aliexpress_affiliate_product_smartmatch_response"),
    METHOD_FEATURED_PROMO_PRODUCTS: lambda: _products_response(
        "aliexpress_affiliate_featuredpromo_products_get_response"
    ),
    METHOD_DS_IMAGE_SEARCH: lambda: _products_response("aliexpress_ds_image_search_response"),
}


@dataclass
class IopCallTracker:
    methods: list[str] = field(default_factory=list)
    requests: list[iop.IopRequest] = field(default_factory=list)


@pytest.fixture
def mock_iop_sdk(monkeypatch):
    tracker = IopCallTracker()
    mock_client = MagicMock(spec=iop.IopClient)

    def fake_execute(request: iop.IopRequest, access_token: str | None = None):
        tracker.methods.append(request._api_pame)
        tracker.requests.append(request)
        response = iop.IopResponse()
        builder = RESPONSE_BY_METHOD.get(request._api_pame)
        response.body = builder() if builder else _empty_products_response("unknown_response")
        return response

    mock_client.execute.side_effect = fake_execute

    aliexpress_api_client_module._build_iop_client.cache_clear()
    get_settings.cache_clear()

    monkeypatch.setenv("ALIEXPRESS_APP_KEY", "test-app-key")
    monkeypatch.setenv("ALIEXPRESS_APP_SECRET", "test-app-secret")
    monkeypatch.setenv("ALIEXPRESS_TRACKING_ID", "test-tracking-id")
    monkeypatch.setenv("ALIEXPRESS_API_URL", "https://api-sg.aliexpress.com/sync")
    monkeypatch.setenv("ALIEXPRESS_ENABLE_DS_IMAGE_SEARCH", "false")

    monkeypatch.setattr(
        aliexpress_api_client_module,
        "_build_iop_client",
        lambda server_url, app_key, app_secret, timeout: mock_client,
    )

    get_settings.cache_clear()
    return tracker, mock_client


def test_aliexpress_api_client_has_no_httpx_or_manual_signing():
    source = inspect.getsource(aliexpress_api_client_module)
    assert "httpx" not in source
    assert "sign_request" not in source
    assert "iop.IopClient" in source or "import iop" in source


def test_iop_sdk_is_used_for_transport(mock_iop_sdk):
    _, mock_client = mock_iop_sdk
    client = aliexpress_api_client_module.AliExpressAPIClient()
    assert client._get_iop_client() is mock_client


@pytest.mark.asyncio
async def test_aliexpress_import_endpoint_uses_iop_sdk(client, mock_iop_sdk):
    tracker, mock_client = mock_iop_sdk
    admin_token = await register_admin(client)

    response = await client.post(
        f"{API_PREFIX}/aliexpress/import",
        headers=auth_headers(admin_token),
        json={"product_id": "1234567890"},
    )

    assert response.status_code == 201
    assert response.json()["aliexpress_product_id"] == "1234567890"
    assert mock_client.execute.called
    assert METHOD_PRODUCT_DETAIL in tracker.methods


@pytest.mark.asyncio
async def test_products_import_url_uses_iop_sdk(client, mock_iop_sdk):
    tracker, mock_client = mock_iop_sdk
    admin_token = await register_admin(client)

    response = await client.post(
        f"{API_PREFIX}/products/import-url",
        headers=auth_headers(admin_token),
        json={"url": "https://www.aliexpress.com/item/1234567890.html"},
    )

    assert response.status_code in (200, 201)
    assert mock_client.execute.called
    assert METHOD_PRODUCT_DETAIL in tracker.methods


@pytest.mark.asyncio
async def test_products_import_uses_iop_sdk(client, mock_iop_sdk):
    tracker, _ = mock_iop_sdk
    admin_token = await register_admin(client)

    response = await client.post(
        f"{API_PREFIX}/products/import",
        headers=auth_headers(admin_token),
        json={"product_id": "1234567890"},
    )

    assert response.status_code in (200, 201)
    assert METHOD_PRODUCT_DETAIL in tracker.methods


@pytest.mark.asyncio
async def test_products_import_batch_uses_iop_sdk(client, mock_iop_sdk):
    tracker, mock_client = mock_iop_sdk
    admin_token = await register_admin(client)

    response = await client.post(
        f"{API_PREFIX}/products/import/batch",
        headers=auth_headers(admin_token),
        json={"product_ids": ["1234567890", "9876543210"]},
    )

    assert response.status_code == 200
    assert mock_client.execute.call_count == 2
    assert tracker.methods.count(METHOD_PRODUCT_DETAIL) == 2


@pytest.mark.asyncio
async def test_discover_endpoints_use_iop_sdk(client, mock_iop_sdk):
    tracker, mock_client = mock_iop_sdk

    cases = [
        (f"{API_PREFIX}/products/discover", METHOD_PRODUCT_QUERY),
        (f"{API_PREFIX}/products/discover/hot", METHOD_HOT_PRODUCT_QUERY),
        (f"{API_PREFIX}/products/discover/deals", METHOD_FEATURED_PROMO_PRODUCTS),
        (f"{API_PREFIX}/products/discover/trending", METHOD_SMART_MATCH),
        (f"{API_PREFIX}/products/discover/category/100003070", METHOD_PRODUCT_QUERY),
        (f"{API_PREFIX}/products/search", METHOD_PRODUCT_QUERY),
    ]

    for index, (path, expected_method) in enumerate(cases):
        tracker.methods.clear()
        mock_client.execute.reset_mock()

        params = {"q": "headphones"} if path.endswith("/search") else None
        response = await client.get(path, params=params)

        assert response.status_code == 200, f"{path} failed: {response.text}"
        assert mock_client.execute.called, f"{path} did not call IOP SDK"
        assert expected_method in tracker.methods, f"{path} expected {expected_method}, got {tracker.methods}"


@pytest.mark.asyncio
async def test_search_image_endpoint_reports_ds_api_requirement(client, mock_iop_sdk):
    _, mock_client = mock_iop_sdk

    response = await client.post(
        f"{API_PREFIX}/products/search/image",
        json={"image_url": "https://example.com/product.jpg"},
    )

    assert response.status_code == 501
    assert mock_client.execute.called is False


@pytest.mark.asyncio
async def test_search_image_uses_iop_sdk_when_enabled(client, mock_iop_sdk, monkeypatch):
    tracker, mock_client = mock_iop_sdk
    monkeypatch.setenv("ALIEXPRESS_ENABLE_DS_IMAGE_SEARCH", "true")
    get_settings.cache_clear()

    response = await client.post(
        f"{API_PREFIX}/products/search/image",
        json={"image_url": "https://example.com/product.jpg"},
    )

    assert response.status_code == 200
    assert mock_client.execute.called
    assert METHOD_DS_IMAGE_SEARCH in tracker.methods


@pytest.mark.asyncio
async def test_iop_requests_are_built_with_add_api_param(client, mock_iop_sdk):
    tracker, _ = mock_iop_sdk
    admin_token = await register_admin(client)

    await client.post(
        f"{API_PREFIX}/products/import",
        headers=auth_headers(admin_token),
        json={"product_id": "1234567890"},
    )

    assert tracker.requests
    request = tracker.requests[-1]
    assert isinstance(request, iop.IopRequest)
    assert request._api_pame == METHOD_PRODUCT_DETAIL
    assert request._api_params["product_ids"] == "1234567890"
    assert "fields" in request._api_params
    assert "tracking_id" in request._api_params
