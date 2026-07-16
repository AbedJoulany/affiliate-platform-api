from decimal import Decimal

from pydantic import BaseModel, Field, HttpUrl, model_validator

from app.aliexpress.types import DiscoveryMode, ProductSortOption
from app.schemas.common import PaginatedResponse
from app.schemas.product import ProductRead


class ProductDiscoveryFilters(BaseModel):
    category_id: str | None = Field(default=None, description="AliExpress category ID")
    min_rating: Decimal | None = Field(default=None, ge=0, le=5)
    min_orders: int | None = Field(default=None, ge=0)
    min_price: Decimal | None = Field(default=None, ge=0)
    max_price: Decimal | None = Field(default=None, ge=0)
    min_discount: Decimal | None = Field(default=None, ge=0, le=100)
    shipping_country: str | None = Field(default=None, min_length=2, max_length=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    choice_only: bool = False
    free_shipping: bool = False
    keywords: str | None = Field(default=None, max_length=255)


class ProductDiscoveryQuery(ProductDiscoveryFilters):
    mode: DiscoveryMode = DiscoveryMode.GENERAL
    sort: ProductSortOption = ProductSortOption.ORDERS_DESC
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=50)
    persist: bool = False
    promotion_name: str | None = Field(default=None, max_length=255)


class DiscoveredProductRead(BaseModel):
    aliexpress_product_id: str
    title: str
    description: str | None = None
    price: Decimal
    original_price: Decimal | None = None
    discount: Decimal
    rating: Decimal
    sales: int
    reviews: int
    image_url: str
    gallery_images: list[str] = Field(default_factory=list)
    product_url: str
    affiliate_url: str | None = None
    category: str | None = None
    store_name: str | None = None
    currency: str = "USD"
    commission_rate: Decimal | None = None
    shipping_info: dict | None = None
    score: Decimal


class ProductDiscoveryResponse(PaginatedResponse):
    items: list[DiscoveredProductRead]
    page: int
    total_pages: int
    mode: DiscoveryMode
    sort: ProductSortOption
    persisted_count: int = 0


class ProductSearchQuery(ProductDiscoveryFilters):
    q: str = Field(min_length=1, max_length=255)
    sort: ProductSortOption = ProductSortOption.ORDERS_DESC
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=50)
    persist: bool = False


class ProductImageSearchRequest(BaseModel):
    image_url: HttpUrl | str | None = None
    image_base64: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=50)
    persist: bool = False

    @model_validator(mode="after")
    def validate_image_source(self) -> "ProductImageSearchRequest":
        if bool(self.image_url) == bool(self.image_base64):
            raise ValueError("Provide exactly one of image_url or image_base64")
        return self


class ProductImportUrlRequest(BaseModel):
    url: HttpUrl | str


class ProductImportRequest(BaseModel):
    url: HttpUrl | str | None = None
    product_id: str | None = None

    @model_validator(mode="after")
    def validate_source(self) -> "ProductImportRequest":
        if bool(self.url) == bool(self.product_id):
            raise ValueError("Provide exactly one of url or product_id")
        return self


class ProductImportBatchRequest(BaseModel):
    product_ids: list[str] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def validate_ids(self) -> "ProductImportBatchRequest":
        for product_id in self.product_ids:
            if not product_id.strip().isdigit():
                raise ValueError("All product_ids must be numeric AliExpress IDs")
        return self


class ProductImportResponse(BaseModel):
    product: ProductRead
    aliexpress_product_id: str
    imported: bool = Field(description="True when created, False when updated")
    image_count: int


class ProductImportBatchResponse(BaseModel):
    imported: int
    updated: int
    failed: int
    products: list[ProductRead]
