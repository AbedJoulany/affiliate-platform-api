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
    title: str
    price: Decimal
    discount: Decimal
    rating: Decimal
    sales: int
    reviews: int
    image_url: str
    product_url: str
    score: Decimal
    status: ProductStatus


class ProductListResponse(PaginatedResponse):
    items: list[ProductRead]
