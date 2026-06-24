from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from app.aliexpress.mapper import AliExpressProductMapper
from app.aliexpress.schemas import AliExpressProductData
from app.aliexpress.signer import sign_request
from app.aliexpress.url_parser import AliExpressURLParser
from app.core.config import Settings, get_settings
from app.services.exceptions import ValidationError

ALIEXPRESS_METHOD = "aliexpress.affiliate.productdetail.get"
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


class AliExpressAPIError(Exception):
    def __init__(self, message: str, *, code: str | int | None = None) -> None:
        self.message = message
        self.code = code
        super().__init__(message)


class AliExpressAffiliateClient:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        mapper: AliExpressProductMapper | None = None,
        url_parser: AliExpressURLParser | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.mapper = mapper or AliExpressProductMapper()
        self.url_parser = url_parser or AliExpressURLParser()

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.aliexpress_app_key and self.settings.aliexpress_app_secret)

    def _ensure_configured(self) -> None:
        if not self.is_configured:
            raise ValidationError("AliExpress App Key and App Secret are not configured")

    async def get_product_details(self, product_id: str) -> AliExpressProductData:
        self._ensure_configured()
        response = await self._call_api(product_ids=product_id)
        product_payload = self._extract_product_payload(response, product_id)
        return self.mapper.map_product(product_id, product_payload)

    async def get_product_details_by_url(self, url: str) -> AliExpressProductData:
        product_id = self.url_parser.extract_product_id(url)
        return await self.get_product_details(product_id)

    async def _call_api(self, **business_params: str) -> dict:
        params = self._build_params(**business_params)
        params["sign"] = sign_request(params, self.settings.aliexpress_app_secret)

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    self.settings.aliexpress_api_url,
                    data=params,
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
                    },
                )
                response.raise_for_status()
                payload = response.json()
            except httpx.HTTPError as exc:
                raise AliExpressAPIError(f"AliExpress API request failed: {exc}") from exc
            except ValueError as exc:
                raise AliExpressAPIError("AliExpress API returned invalid JSON") from exc

        self._raise_for_api_errors(payload)
        return payload

    def _build_params(self, **business_params: str) -> dict[str, str]:
        timestamp = datetime.now(SHANGHAI_TZ).strftime("%Y-%m-%d %H:%M:%S")
        params: dict[str, str] = {
            "method": ALIEXPRESS_METHOD,
            "app_key": self.settings.aliexpress_app_key,
            "sign_method": "md5",
            "timestamp": timestamp,
            "format": "json",
            "v": "2.0",
            "target_currency": self.settings.aliexpress_target_currency,
            "target_language": self.settings.aliexpress_target_language,
            "country": self.settings.aliexpress_country,
            "fields": (
                "commission_rate,discount,evaluate_rate,lastest_volume,product_title,"
                "product_main_image_url,product_small_image_urls,promotion_link,"
                "product_detail_url,target_sale_price,target_original_price,"
                "target_sale_price_currency,sale_price,original_price"
            ),
        }
        if self.settings.aliexpress_tracking_id:
            params["tracking_id"] = self.settings.aliexpress_tracking_id
        params.update({key: str(value) for key, value in business_params.items() if value})
        return params

    def _extract_product_payload(self, response: dict, product_id: str) -> dict:
        root = response.get("aliexpress_affiliate_productdetail_get_response", response)
        result_container = root.get("resp_result") or root.get("result") or root

        if isinstance(result_container, dict) and result_container.get("resp_code") not in (
            None,
            200,
            "200",
        ):
            raise AliExpressAPIError(
                str(result_container.get("resp_msg") or "AliExpress API call failed"),
                code=result_container.get("resp_code"),
            )

        result = result_container.get("result") if isinstance(result_container, dict) else None
        if not isinstance(result, dict):
            result = result_container if isinstance(result_container, dict) else {}

        products = result.get("products") or {}
        product_list = products.get("product") if isinstance(products, dict) else products
        if product_list is None:
            product_list = result.get("product")

        if isinstance(product_list, dict):
            product_list = [product_list]
        if not isinstance(product_list, list) or not product_list:
            raise AliExpressAPIError(f"AliExpress product {product_id} was not found")

        for item in product_list:
            if not isinstance(item, dict):
                continue
            current_id = str(item.get("product_id") or product_id)
            if current_id == str(product_id):
                return item

        first = product_list[0]
        if isinstance(first, dict):
            return first
        raise AliExpressAPIError(f"AliExpress product {product_id} was not found")

    def _raise_for_api_errors(self, response: dict) -> None:
        if "error_response" in response:
            error = response["error_response"]
            raise AliExpressAPIError(
                str(error.get("msg") or error.get("sub_msg") or "AliExpress API error"),
                code=error.get("code") or error.get("sub_code"),
            )

        root = response.get("aliexpress_affiliate_productdetail_get_response", {})
        if isinstance(root, dict) and root.get("error_code"):
            raise AliExpressAPIError(
                str(root.get("error_msg") or "AliExpress API error"),
                code=root.get("error_code"),
            )
