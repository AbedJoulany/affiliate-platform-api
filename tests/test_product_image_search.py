"""Global product image search — no workspace membership or X-Workspace-Id required.

The AliExpress client is mocked at the service/client boundary. Tests never call
the real DS API.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.aliexpress.client import AliExpressAffiliateClient
from app.aliexpress.exceptions import AliExpressAPIError
from app.aliexpress.response_parser import AliExpressPageMeta
from app.aliexpress.schemas import AliExpressProductData

API_PREFIX = "/api/v1"
IMAGE_SEARCH = f"{API_PREFIX}/products/search/image"


def _meta(*, total: int = 0) -> AliExpressPageMeta:
    return AliExpressPageMeta(
        current_page=1,
        total_pages=1 if total else 1,
        current_count=total,
        total_count=total,
        is_finished=True,
    )


def _product() -> AliExpressProductData:
    return AliExpressProductData(
        aliexpress_product_id="1234567890",
        title="Wireless Earbuds",
        image_url="https://example.com/main.jpg",
        images=["https://example.com/main.jpg", "https://example.com/alt.jpg"],
        price=Decimal("29.99"),
        product_url="https://www.aliexpress.com/item/1234567890.html",
    )


def _stub_search(monkeypatch, handler):
    monkeypatch.setattr(AliExpressAffiliateClient, "search_products_by_image", handler)


@pytest.mark.asyncio
async def test_image_search_returns_normalized_products(client, monkeypatch):
    async def fake_search(self, *, image_url=None, image_base64=None):
        assert image_url == "https://example.com/product.jpg"
        assert image_base64 is None
        return [_product()], _meta(total=1)

    _stub_search(monkeypatch, fake_search)

    response = await client.post(
        IMAGE_SEARCH,
        json={"image_url": "https://example.com/product.jpg"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["aliexpress_product_id"] == "1234567890"
    assert item["image_url"] == "https://example.com/main.jpg"
    assert item["gallery_images"] == [
        "https://example.com/main.jpg",
        "https://example.com/alt.jpg",
    ]


@pytest.mark.asyncio
async def test_image_search_rejects_empty_query(client):
    response = await client.post(IMAGE_SEARCH, json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_image_search_rejects_both_image_sources(client):
    response = await client.post(
        IMAGE_SEARCH,
        json={
            "image_url": "https://example.com/product.jpg",
            "image_base64": "abc",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_image_search_empty_results_are_success(client, monkeypatch):
    async def fake_search(self, *, image_url=None, image_base64=None):
        return [], _meta(total=0)

    _stub_search(monkeypatch, fake_search)

    response = await client.post(
        IMAGE_SEARCH,
        json={"image_url": "https://example.com/product.jpg"},
    )

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["total"] == 0


@pytest.mark.asyncio
async def test_image_search_provider_failure_is_502(client, monkeypatch):
    async def fake_search(self, *, image_url=None, image_base64=None):
        raise AliExpressAPIError("provider unavailable")

    _stub_search(monkeypatch, fake_search)

    response = await client.post(
        IMAGE_SEARCH,
        json={"image_url": "https://example.com/product.jpg"},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "provider unavailable"


@pytest.mark.asyncio
async def test_image_search_works_without_auth_or_workspace_header(client, monkeypatch):
    async def fake_search(self, *, image_url=None, image_base64=None):
        return [_product()], _meta(total=1)

    _stub_search(monkeypatch, fake_search)

    response = await client.post(
        IMAGE_SEARCH,
        json={"image_url": "https://example.com/product.jpg"},
    )

    assert response.status_code == 200
    assert "x-workspace-id" not in {key.lower() for key in response.request.headers}


@pytest.mark.asyncio
async def test_image_search_ignores_workspace_header_and_membership(client, monkeypatch):
    async def fake_search(self, *, image_url=None, image_base64=None):
        return [_product()], _meta(total=1)

    _stub_search(monkeypatch, fake_search)

    response = await client.post(
        IMAGE_SEARCH,
        headers={"X-Workspace-Id": str(uuid4())},
        json={"image_url": "https://example.com/product.jpg"},
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["aliexpress_product_id"] == "1234567890"
