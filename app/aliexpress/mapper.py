import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from app.aliexpress.schemas import AliExpressProductData
from app.aliexpress.url_parser import AliExpressURLParser

PERCENT_PATTERN = re.compile(r"([\d.]+)\s*%?")


class AliExpressProductMapper:
    def __init__(self, url_parser: AliExpressURLParser | None = None) -> None:
        self.url_parser = url_parser or AliExpressURLParser()

    def map_product(
        self,
        product_id: str,
        payload: dict,
    ) -> AliExpressProductData:
        # --- NEW SAFEGUARD FOR NESTED LOOKUPS (Product Details) ---
        if "product_info" in payload:
            payload = payload["product_info"]
        elif "aeop_ae_product_info" in payload:
            payload = payload["aeop_ae_product_info"]
        # -----------------------------------------------------------

        title = str(payload.get("product_title") or payload.get("title") or "").strip()
        if not title:
            raise ValueError("AliExpress product title is missing from API response")

        image_url = self._extract_main_image(payload)
        images = self._extract_images(payload, image_url)
        price = self._to_decimal(payload.get("target_sale_price") or payload.get("sale_price"))
        original_price = self._to_decimal_optional(
            payload.get("target_original_price") or payload.get("original_price")
        )
        discount = self._resolve_discount(payload, price, original_price)
        rating = self._resolve_rating(payload.get("evaluate_rate"))
        sales = self._to_int(payload.get("lastest_volume") or payload.get("volume"))
        reviews = self._to_int(payload.get("review_number") or payload.get("reviews"))

        promotion_url = payload.get("promotion_link") or payload.get("promo_link")
        product_url = (
            payload.get("product_detail_url")
            or promotion_url
            or self.url_parser.build_product_url(product_id)
        )

        category_name = payload.get("second_level_category_name") or payload.get(
            "first_level_category_name"
        )
        category_id = payload.get("second_level_category_id") or payload.get(
            "first_level_category_id"
        )

        commission_rate = self._to_decimal_optional(
            payload.get("hot_product_commission_rate")
            or payload.get("commission_rate")
            or payload.get("relevant_market_commission_rate")
        )

        shipping_info = self._build_shipping_info(payload)

        return AliExpressProductData(
            aliexpress_product_id=product_id,
            title=title[:255],
            image_url=image_url,
            images=images,
            price=price,
            original_price=original_price,
            discount=discount,
            rating=rating,
            sales=sales,
            reviews=reviews,
            product_url=str(product_url),
            promotion_url=str(promotion_url) if promotion_url else None,
            currency=str(
                payload.get("target_sale_price_currency")
                or payload.get("sale_price_currency")
                or "USD"
            ),
            description=str(
                payload.get("product_description") or payload.get("description") or ""
            ).strip()
            or None,
            category=str(category_name).strip() if category_name else None,
            category_id=str(category_id) if category_id not in (None, "") else None,
            store_name=self._extract_store_name(payload),
            commission_rate=commission_rate,
            shipping_info=shipping_info,
            platform_product_type=str(payload.get("platform_product_type") or "") or None,
            last_synced_at=datetime.now(UTC),
        )

    def _extract_main_image(self, payload: dict) -> str:
        for key in ("product_main_image_url", "product_main_image", "main_image"):
            value = payload.get(key)
            if value:
                return str(value)

        images = self._extract_images(payload, "")
        if not images:
            raise ValueError("AliExpress product image is missing from API response")
        return images[0]

    def _extract_images(self, payload: dict, fallback: str) -> list[str]:
        images: list[str] = []
        small_urls = payload.get("product_small_image_urls")
        if isinstance(small_urls, dict):
            raw = small_urls.get("string") or small_urls.get("product_small_image_url")
            if isinstance(raw, list):
                images.extend(str(item) for item in raw if item)
            elif raw:
                images.append(str(raw))
        elif isinstance(small_urls, list):
            images.extend(str(item) for item in small_urls if item)

        if fallback and fallback not in images:
            images.insert(0, fallback)
        return images

    def _extract_store_name(self, payload: dict) -> str | None:
        for key in ("shop_name", "store_name", "seller_name"):
            value = payload.get(key)
            if value:
                return str(value)[:255]
        shop_url = payload.get("shop_url")
        if shop_url:
            return str(shop_url)[:255]
        return None

    def _build_shipping_info(self, payload: dict) -> dict | None:
        shipping: dict[str, str | int | bool] = {}
        ship_to_days = payload.get("ship_to_days")
        if ship_to_days not in (None, ""):
            shipping["ship_to_days"] = str(ship_to_days)
        if payload.get("free_shipping") in ("Y", "y", True):
            shipping["free_shipping"] = True
        if payload.get("ship_to_country"):
            shipping["ship_to_country"] = str(payload.get("ship_to_country"))
        return shipping or None

    def _resolve_discount(
        self,
        payload: dict,
        price: Decimal,
        original_price: Decimal | None,
    ) -> Decimal:
        raw_discount = payload.get("discount")
        if raw_discount:
            parsed = self._parse_percent(raw_discount)
            if parsed is not None:
                return parsed

        if original_price and original_price > 0 and price < original_price:
            return ((original_price - price) / original_price * Decimal("100")).quantize(
                Decimal("0.01")
            )
        return Decimal("0.00")

    def _resolve_rating(self, evaluate_rate: object) -> Decimal:
        parsed = self._parse_percent(evaluate_rate)
        if parsed is None:
            return Decimal("0.00")
        return (parsed / Decimal("20")).quantize(Decimal("0.01"))

    def _parse_percent(self, value: object) -> Decimal | None:
        if value is None:
            return None
        if isinstance(value, (int, float, Decimal)):
            return Decimal(str(value)).quantize(Decimal("0.01"))
        match = PERCENT_PATTERN.search(str(value))
        if not match:
            return None
        return Decimal(match.group(1)).quantize(Decimal("0.01"))

    def _to_decimal(self, value: object) -> Decimal:
        parsed = self._to_decimal_optional(value)
        return parsed if parsed is not None else Decimal("0.00")

    def _to_decimal_optional(self, value: object) -> Decimal | None:
        if value is None or value == "":
            return None
        try:
            return Decimal(str(value)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            return None

    def _to_int(self, value: object) -> int:
        if value is None or value == "":
            return 0
        try:
            return int(str(value))
        except ValueError:
            return 0
