from unittest.mock import MagicMock, patch

import iop
import pytest

from app.aliexpress.api_client import AliExpressAPIClient
from app.aliexpress.constants import METHOD_PRODUCT_QUERY
from app.aliexpress.exceptions import AliExpressAPIError
from app.aliexpress.response_parser import extract_products_and_meta
from app.core.config import Settings


def test_extract_products_and_meta_parses_cursor_response():
    payload = {
        "aliexpress_affiliate_product_query_response": {
            "resp_result": {
                "resp_code": 200,
                "result": {
                    "products": [
                        {"product_id": 1001, "product_title": "Sample Product"},
                        {"product_id": 1002, "product_title": "Another Product"},
                    ],
                    "current_page_no": 2,
                    "total_page_no": 5,
                    "current_record_count": 2,
                    "total_record_count": 10,
                    "is_finished": False,
                },
            }
        }
    }

    products, meta = extract_products_and_meta(payload, METHOD_PRODUCT_QUERY)

    assert len(products) == 2
    assert products[0]["product_id"] == 1001
    assert meta.current_page == 2
    assert meta.total_pages == 5
    assert meta.total_count == 10
    assert meta.is_finished is False


def test_extract_products_and_meta_raises_on_api_error():
    payload = {"error_response": {"code": 29, "msg": "Invalid app key"}}

    with pytest.raises(AliExpressAPIError):
        extract_products_and_meta(payload, METHOD_PRODUCT_QUERY)


def test_client_builds_iop_request_with_business_params():
    settings = Settings(
        aliexpress_app_key="app-key",
        aliexpress_app_secret="app-secret",
        aliexpress_tracking_id="tracking-id",
        aliexpress_target_currency="USD",
        aliexpress_target_language="EN",
        aliexpress_country="US",
    )
    client = AliExpressAPIClient(settings)
    request = client._build_request(METHOD_PRODUCT_QUERY, keywords="headphones")

    assert request._api_pame == METHOD_PRODUCT_QUERY
    assert request._api_params["tracking_id"] == "tracking-id"
    assert request._api_params["keywords"] == "headphones"
    assert request._api_params["target_currency"] == "USD"


@pytest.mark.asyncio
async def test_call_method_uses_iop_sdk_execute():
    settings = Settings(
        aliexpress_app_key="app-key",
        aliexpress_app_secret="app-secret",
        aliexpress_api_url="https://api-sg.aliexpress.com/sync",
    )
    client = AliExpressAPIClient(settings)

    mock_response = iop.IopResponse()
    mock_response.body = {
        "aliexpress_affiliate_product_query_response": {
            "resp_result": {"resp_code": 200, "result": {"products": []}},
        }
    }

    mock_iop_client = MagicMock()
    mock_iop_client.execute.return_value = mock_response

    with patch.object(client, "_get_iop_client", return_value=mock_iop_client):
        payload = await client.call_method(METHOD_PRODUCT_QUERY, keywords="phone")

    mock_iop_client.execute.assert_called_once()
    request = mock_iop_client.execute.call_args.args[0]
    assert isinstance(request, iop.IopRequest)
    assert request._api_pame == METHOD_PRODUCT_QUERY
    assert request._api_params["keywords"] == "phone"
    assert "products" in str(payload) or "aliexpress_affiliate_product_query_response" in payload
