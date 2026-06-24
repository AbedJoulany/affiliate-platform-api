import hashlib
import re
from urllib.parse import parse_qs, urlparse

ALIEXPRESS_ITEM_PATH = re.compile(r"/item/(?P<product_id>\d+)\.html?", re.IGNORECASE)
ALIEXPRESS_SHORT_PATH = re.compile(r"/i/(?P<product_id>\d+)\.html?", re.IGNORECASE)


class AliExpressURLParser:
    def extract_product_id(self, value: str) -> str:
        raw = value.strip()
        if raw.isdigit():
            return raw

        parsed = urlparse(raw if "://" in raw else f"https://{raw}")
        host = (parsed.netloc or "").lower()

        if host and "aliexpress" not in host:
            raise ValueError("URL must be a valid AliExpress product link")

        for pattern in (ALIEXPRESS_ITEM_PATH, ALIEXPRESS_SHORT_PATH):
            match = pattern.search(parsed.path)
            if match:
                return match.group("product_id")

        query = parse_qs(parsed.query)
        for key in ("productId", "product_id", "item_id"):
            if key in query and query[key][0].isdigit():
                return query[key][0]

        raise ValueError("Could not extract AliExpress product ID from URL")

    def build_product_url(self, product_id: str) -> str:
        return f"https://www.aliexpress.com/item/{product_id}.html"
