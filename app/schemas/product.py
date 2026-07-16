from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from app.core.enums import ProductStatus
from app.schemas.common import PaginatedResponse, TimestampSchema


class ProductCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    price: Decimal = Field(ge=0)
    discount: Decimal = Field(default=Decimal("0.00"), ge=0, le=100)
    rating: Decimal = Field(default=Decimal("0.00"), ge=0, le=5)
    sales: int = Field(default=0, ge=0)
    reviews: int = Field(default=0, ge=0)
    image_url: HttpUrl | str
    product_url: HttpUrl | str
    score: Decimal = Field(default=Decimal("0.0000"), ge=0)
    status: ProductStatus = ProductStatus.DRAFT


class ProductUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    price: Decimal | None = Field(default=None, ge=0)
    discount: Decimal | None = Field(default=None, ge=0, le=100)
    rating: Decimal | None = Field(default=None, ge=0, le=5)
    sales: int | None = Field(default=None, ge=0)
    reviews: int | None = Field(default=None, ge=0)
    image_url: HttpUrl | str | None = None
    product_url: HttpUrl | str | None = None
    score: Decimal | None = Field(default=None, ge=0)
    status: ProductStatus | None = None


class ProductRead(TimestampSchema):
    id: UUID
    aliexpress_product_id: str | None = None
    title: str
    description: str | None = None
    price: Decimal
    original_price: Decimal | None = None
    discount: Decimal
    rating: Decimal
    sales: int
    reviews: int
    image_url: str
    gallery_images: list[str] | None = None
    product_url: str
    affiliate_url: str | None = None
    category: str | None = None
    store_name: str | None = None
    currency: str = "USD"
    commission_rate: Decimal | None = None
    shipping_info: dict | None = None
    score: Decimal
    status: ProductStatus
    last_synced_at: datetime | None = None


class ProductListResponse(PaginatedResponse):
    items: list[ProductRead]
