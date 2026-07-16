import asyncio
import json
import random
from functools import lru_cache
from typing import Any
from urllib import response

import iop

from app.aliexpress.constants import FAVORITE_PRODUCT_FIELDS
from app.aliexpress.exceptions import (
    AliExpressAPIError,
    AliExpressCredentialsError,
    AliExpressRateLimitError,
)
from app.aliexpress.response_parser import (
    AliExpressPageMeta,
    extract_categories,
    extract_products_and_meta,
    extract_promotions,
)
from app.core.config import Settings, get_settings
from app.services.exceptions import ValidationError

RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504}
CREDENTIAL_ERROR_CODES = {"27", "29", 27, 29, "invalid_app_key", "invalid-sessionkey"}


@lru_cache
def _build_iop_client(
    server_url: str,
    app_key: str,
    app_secret: str,
    timeout: float,
) -> iop.IopClient:
    return iop.IopClient("https://api-sg.aliexpress.com/sync", app_key, app_secret, timeout=timeout)


class AliExpressAPIClient:
    """Reusable AliExpress Open Platform client backed by the official IOP SDK."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._rate_limit_lock = asyncio.Lock()
        self._last_request_at: float | None = None
        self._iop_client: iop.IopClient | None = None

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.aliexpress_app_key and self.settings.aliexpress_app_secret)

    def _ensure_configured(self) -> None:
        if not self.is_configured:
            raise ValidationError("AliExpress App Key and App Secret are not configured")

    def _get_iop_client(self) -> iop.IopClient:
        self._ensure_configured()
        if self._iop_client is None:
            self._iop_client = _build_iop_client(
                "https://api-sg.aliexpress.com/sync",
                self.settings.aliexpress_app_key,
                self.settings.aliexpress_app_secret,
                self.settings.aliexpress_request_timeout,
            )
        return self._iop_client

    async def call_method(
        self,
        method: str,
        *,
        fields: str | None = None,
        **business_params: str | int | float | bool | None,
    ) -> dict:
        request = self._build_request(
            method,
            fields=fields,
            **business_params,
        )
        return await self._execute_with_retries(request)

    async def fetch_products_page(
        self,
        method: str,
        *,
        page_no: int = 1,
        page_size: int = 20,
        fields: str | None = None,
        **business_params: str | int | float | bool | None,
    ) -> tuple[list[dict], AliExpressPageMeta]:
        payload = await self.call_method(
            method,
            fields=fields,
            page_no=str(page_no),
            page_size=str(min(max(page_size, 1), 50)),
            **business_params,
        )
        return extract_products_and_meta(payload, method)

    async def fetch_all_products(
        self,
        method: str,
        *,
        page_size: int = 50,
        max_pages: int = 10,
        fields: str | None = None,
        **business_params: str | int | float | bool | None,
    ) -> list[dict]:
        products: list[dict] = []
        page_no = 1

        while page_no <= max_pages:
            page_products, meta = await self.fetch_products_page(
                method,
                page_no=page_no,
                page_size=page_size,
                fields=fields,
                **business_params,
            )
            products.extend(page_products)
            if meta.is_finished or not page_products or page_no >= meta.total_pages:
                break
            page_no += 1

        return products

    async def fetch_categories(self, method: str) -> list[dict]:
        payload = await self.call_method(method)
        return extract_categories(payload, method)

    async def fetch_promotions(self, method: str) -> list[dict]:
        payload = await self.call_method(method)
        return extract_promotions(payload, method)

    def _build_request(
        self,
        method: str,
        *,
        fields: str | None = None,
        **business_params: str | int | float | bool | None,
    ) -> iop.IopRequest:

        request = iop.IopRequest(method)

        params_debug = {}

        def add(k, v):
            request.add_api_param(k, v)
            params_debug[k] = v

        add("target_currency", self.settings.aliexpress_target_currency)
        add("target_language", self.settings.aliexpress_target_language)
        add("country", self.settings.aliexpress_country)
        add("fields", fields or FAVORITE_PRODUCT_FIELDS)

        if self.settings.aliexpress_tracking_id:
            add("tracking_id", self.settings.aliexpress_tracking_id)

        for key, value in business_params.items():
            if value is None:
                continue
            add(key, value)

        print("\n🔥 RAW REQUEST PARAMS (BEFORE SIGN):")
        for k, v in sorted(params_debug.items()):
            print(f"{k} = {v}")

        print("\n🔥 METHOD:", method)

        return request

    async def _execute_with_retries(self, request: iop.IopRequest) -> dict:
        max_retries = self.settings.aliexpress_max_retries
        last_error: Exception | None = None

        for attempt in range(max_retries + 1):
            await self._apply_rate_limit()
            try:
                payload = await self._execute_once(request)
                self._raise_for_top_level_errors(payload)
                return payload
            except AliExpressCredentialsError:
                raise
            except AliExpressRateLimitError as exc:
                last_error = exc
                if attempt >= max_retries:
                    break
                await asyncio.sleep(self._backoff_seconds(attempt))
            except AliExpressAPIError as exc:
                last_error = exc
                if attempt >= max_retries or not self._is_retryable(exc):
                    break
                await asyncio.sleep(self._backoff_seconds(attempt))

        if last_error is None:
            raise AliExpressAPIError("AliExpress API request failed")
        if isinstance(last_error, AliExpressAPIError):
            raise last_error
        raise AliExpressAPIError(f"AliExpress API request failed: {last_error}") from last_error

    async def _execute_once(self, request: iop.IopRequest) -> dict:
        client = self._get_iop_client()
        try:
            response = await asyncio.to_thread(client.execute, request)
            print("=== RAW IOP RESPONSE BODY ===")
            print(response.body)
        except Exception as exc:
            message = str(exc)
            if "429" in message or "rate limit" in message.lower():
                raise AliExpressRateLimitError(message, code=429) from exc
            if any(str(code) in message for code in RETRYABLE_STATUS_CODES):
                raise AliExpressAPIError(message) from exc
            raise AliExpressAPIError(f"AliExpress IOP SDK request failed: {message}") from exc

        return self._parse_iop_response(response)

    def _parse_iop_response(self, response: iop.IopResponse) -> dict:
        if response.code and response.code not in ("", "0"):
            message = response.message or "AliExpress API error"
            if response.code in {str(code) for code in CREDENTIAL_ERROR_CODES} or "invalid app" in message.lower():
                raise AliExpressCredentialsError(message, code=response.code)
            if response.code in {"429", "503"} or "rate limit" in message.lower():
                raise AliExpressRateLimitError(message, code=response.code)
            raise AliExpressAPIError(message, code=response.code)

        body = response.body
        if body is None:
            raise AliExpressAPIError("AliExpress API returned an empty response")
        if isinstance(body, str):
            try:
                parsed = json.loads(body)
            except ValueError as exc:
                raise AliExpressAPIError("AliExpress API returned invalid JSON") from exc
            return parsed
        if isinstance(body, dict):
            return body
        raise AliExpressAPIError("AliExpress API returned an unexpected response type")

    async def _apply_rate_limit(self) -> None:
        min_interval = self.settings.aliexpress_rate_limit_interval_seconds
        if min_interval <= 0:
            return

        async with self._rate_limit_lock:
            loop = asyncio.get_running_loop()
            now = loop.time()
            if self._last_request_at is not None:
                elapsed = now - self._last_request_at
                if elapsed < min_interval:
                    await asyncio.sleep(min_interval - elapsed)
            self._last_request_at = loop.time()

    def _backoff_seconds(self, attempt: int) -> float:
        base = self.settings.aliexpress_retry_backoff_seconds
        return base * (2**attempt) + random.uniform(0, 0.25)

    def _is_retryable(self, exc: Exception) -> bool:
        if isinstance(exc, AliExpressRateLimitError):
            return True
        if isinstance(exc, AliExpressAPIError):
            if exc.code in RETRYABLE_STATUS_CODES:
                return True
            message = exc.message.lower()
            return "timeout" in message or "temporarily" in message
        return False

    def _raise_for_top_level_errors(self, payload: dict[str, Any]) -> None:
        if "error_response" not in payload:
            return

        error = payload["error_response"]
        code = error.get("code") or error.get("sub_code")
        message = str(error.get("msg") or error.get("sub_msg") or "AliExpress API error")

        if code in CREDENTIAL_ERROR_CODES or "invalid app" in message.lower():
            raise AliExpressCredentialsError(message, code=code)
        if code in (429, "429") or "rate limit" in message.lower():
            raise AliExpressRateLimitError(message, code=code)
        raise AliExpressAPIError(message, code=code)
