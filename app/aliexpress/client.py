from app.aliexpress.api_client import AliExpressAPIClient
from app.aliexpress.constants import (
    METHOD_CATEGORY_GET,
    METHOD_DS_IMAGE_SEARCH,
    METHOD_FEATURED_PROMO,
    METHOD_FEATURED_PROMO_PRODUCTS,
    METHOD_HOT_PRODUCT_QUERY,
    METHOD_LINK_GENERATE,
    METHOD_PRODUCT_DETAIL,
    METHOD_PRODUCT_QUERY,
    METHOD_SMART_MATCH,
)
from app.aliexpress.exceptions import (
    AliExpressAPIError,  # noqa: F401
    AliExpressImageSearchNotSupportedError,
)
from app.aliexpress.mapper import AliExpressProductMapper
from app.aliexpress.response_parser import (
    AliExpressPageMeta,
    extract_products_and_meta,
    extract_response_root,
    extract_result_payload,
    normalize_product_list,
)
from app.aliexpress.schemas import AliExpressProductData
from app.aliexpress.types import AliExpressAPISort, AliExpressPromoSort, PlatformProductType
from app.aliexpress.url_parser import AliExpressURLParser


class AliExpressAffiliateClient(AliExpressAPIClient):
    """Affiliate API facade built on the shared AliExpress API client."""

    def __init__(
        self,
        settings=None,
        *,
        mapper: AliExpressProductMapper | None = None,
        url_parser: AliExpressURLParser | None = None,
    ) -> None:
        super().__init__(settings)
        self.mapper = mapper or AliExpressProductMapper()
        self.url_parser = url_parser or AliExpressURLParser()

    async def get_product_details(self, product_id: str) -> AliExpressProductData:
        response = await self.call_method(METHOD_PRODUCT_DETAIL, product_ids=product_id)
        product_payload = self._extract_single_product_payload(response, product_id)
        return self.mapper.map_product(product_id, product_payload)

    async def get_product_details_by_url(self, url: str) -> AliExpressProductData:
        product_id = self.url_parser.extract_product_id(url)
        return await self.get_product_details(product_id)

    async def query_products(
        self,
        *,
        page_no: int = 1,
        page_size: int = 20,
        category_ids: str | None = None,
        keywords: str | None = None,
        min_sale_price: str | None = None,
        max_sale_price: str | None = None,
        sort: AliExpressAPISort | str | None = None,
        platform_product_type: PlatformProductType | str | None = None,
        ship_to_country: str | None = None,
        delivery_days: str | None = None,
    ) -> tuple[list[AliExpressProductData], AliExpressPageMeta]:
        raw_products, meta = await self.fetch_products_page(
            METHOD_PRODUCT_QUERY,
            page_no=page_no,
            page_size=page_size,
            category_ids=category_ids,
            keywords=keywords,
            min_sale_price=min_sale_price,
            max_sale_price=max_sale_price,
            sort=sort.value if isinstance(sort, AliExpressAPISort) else sort,
            platform_product_type=(
                platform_product_type.value
                if isinstance(platform_product_type, PlatformProductType)
                else platform_product_type
            ),
            ship_to_country=ship_to_country or self.settings.aliexpress_country,
            delivery_days=delivery_days,
        )
        return self._map_products(raw_products), meta

    async def get_hot_products(
        self,
        *,
        page_no: int = 1,
        page_size: int = 20,
        category_ids: str | None = None,
        keywords: str | None = None,
        sort: AliExpressAPISort | str | None = AliExpressAPISort.LAST_VOLUME_DESC,
        ship_to_country: str | None = None,
    ) -> tuple[list[AliExpressProductData], AliExpressPageMeta]:
        raw_products, meta = await self.fetch_products_page(
            METHOD_HOT_PRODUCT_QUERY,
            page_no=page_no,
            page_size=page_size,
            category_ids=category_ids,
            keywords=keywords,
            sort=sort.value if isinstance(sort, AliExpressAPISort) else sort,
            ship_to_country=ship_to_country or self.settings.aliexpress_country,
        )
        return self._map_products(raw_products), meta

    async def get_trending_products(
        self,
        *,
        page_no: int = 1,
        page_size: int = 20,
        keywords: str | None = None,
        product_id: str | None = None,
        device_id: str | None = None,
        ship_to_country: str | None = None,
    ) -> tuple[list[AliExpressProductData], AliExpressPageMeta]:
        raw_products, meta = await self.fetch_products_page(
            METHOD_SMART_MATCH,
            page_no=page_no,
            page_size=page_size,
            keywords=keywords,
            product_id=product_id,
            device_id=device_id or self.settings.aliexpress_smartmatch_device_id,
            ship_to_country=ship_to_country or self.settings.aliexpress_country,
        )
        return self._map_products(raw_products), meta

    async def get_featured_promo_products(
        self,
        *,
        page_no: int = 1,
        page_size: int = 20,
        category_id: str | None = None,
        promotion_name: str | None = None,
        sort: AliExpressPromoSort | str | None = None,
        country: str | None = None,
    ) -> tuple[list[AliExpressProductData], AliExpressPageMeta]:
        raw_products, meta = await self.fetch_products_page(
            METHOD_FEATURED_PROMO_PRODUCTS,
            page_no=page_no,
            page_size=page_size,
            category_id=category_id,
            promotion_name=promotion_name,
            sort=sort.value if isinstance(sort, AliExpressPromoSort) else sort,
            country=country or self.settings.aliexpress_country,
        )
        return self._map_products(raw_products), meta

    async def get_featured_promotions(self) -> list[dict]:
        return await self.fetch_promotions(METHOD_FEATURED_PROMO)

    async def get_categories(self) -> list[dict]:
        return await self.fetch_categories(METHOD_CATEGORY_GET)

    async def search_products_by_image(
        self,
        *,
        image_url: str | None = None,
        image_base64: str | None = None,
    ) -> tuple[list[AliExpressProductData], AliExpressPageMeta]:
        if not self.settings.aliexpress_enable_ds_image_search:
            raise AliExpressImageSearchNotSupportedError(
                "Image search requires AliExpress DS API access. "
                "Set ALIEXPRESS_ENABLE_DS_IMAGE_SEARCH=true after enabling "
                "aliexpress.ds.image.search."
            )
        if not image_url and not image_base64:
            raise AliExpressAPIError("Provide image_url or image_base64 for image search")

        params: dict[str, str | None] = {}
        if image_url:
            params["image_url"] = image_url
        if image_base64:
            params["image_base64"] = image_base64

        payload = await self.call_method(METHOD_DS_IMAGE_SEARCH, **params)
        raw_products, meta = extract_products_and_meta(payload, METHOD_DS_IMAGE_SEARCH)
        return self._map_products(raw_products), meta

    def _map_products(self, raw_products: list[dict]) -> list[AliExpressProductData]:
        mapped: list[AliExpressProductData] = []
        for payload in raw_products:
            # --- NESTING SAFEGUARD ---
            # Unpack wrapped inner info blocks before looking for the product ID.
            if "product_info" in payload:
                payload = payload["product_info"]
            elif "aeop_ae_product_info" in payload:
                payload = payload["aeop_ae_product_info"]
            # --------------------------

            product_id = str(
                payload.get("product_id") or payload.get("aliexpress_product_id") or ""
            ).strip()
            if not product_id:
                continue
            try:
                mapped.append(self.mapper.map_product(product_id, payload))
            except ValueError:
                continue
        return mapped

    def _extract_single_product_payload(self, response: dict, product_id: str) -> dict:
        root = extract_response_root(response, METHOD_PRODUCT_DETAIL)
        result = extract_result_payload(root)
        
        product_list = normalize_product_list(result.get("products"))
        if not product_list:
            product_list = normalize_product_list(result.get("product"))

        if not product_list:
            raise AliExpressAPIError(f"AliExpress product {product_id} was not found")

        # Find the targeted item out of the detail array safely
        for item in product_list:
            # Flatten context checks here too
            inner_item = item.get("product_info") or item.get("aeop_ae_product_info") or item
            current_id = str(
                inner_item.get("product_id")
                or inner_item.get("aliexpress_product_id")
                or product_id
            )
            if current_id == str(product_id):
                return item

        return product_list[0]
    
    async def generate_short_link(self, long_url: str, tracking_id: str = "default") -> str:
            """
            Converts a long affiliate promotion link into a clean short link.
            """
            params = {
                "source_values": long_url,
                "promotion_link_type": "0",  # 0 indicates standardized short link format
                "tracking_id": tracking_id
            }
            
            try:
                # Assumes METHOD_LINK_GENERATE evaluates to "aliexpress.affiliate.link.generate"
                payload = await self.call_method(METHOD_LINK_GENERATE, **params)
                
                from app.aliexpress.response_parser import (
                    extract_response_root,
                    extract_result_payload,
                )
                root = extract_response_root(payload, METHOD_LINK_GENERATE)
                result = extract_result_payload(root)
                
                # Match the dictionary matching your verified payload layout:
                # result -> {"promotion_links": {"promotion_link": [...]}}
                promo_links_container = result.get("promotion_links") or {}
                links = promo_links_container.get("promotion_link", [])
                
                if links and isinstance(links, list):
                    # Pull the link string directly from 'promotion_link'
                    short_url = links[0].get("promotion_link")
                    if short_url:
                        return str(short_url)
                    
                return long_url
            except Exception:
                # Fallback gracefully to the long URL if the shortening request fails
                return long_url
