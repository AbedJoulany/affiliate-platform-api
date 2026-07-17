from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl, model_validator

from app.schemas.common import ORMModel
from app.schemas.product import ProductRead


class AliExpressCategoryRead(ORMModel):
    category_id: int
    category_name: str
    parent_category_id: int
    synced_at: datetime


class AliExpressCategoryListResponse(BaseModel):
    items: list[AliExpressCategoryRead]
    total: int
    synced_at: datetime | None


class AliExpressImportRequest(BaseModel):
    url: HttpUrl | str | None = Field(
        default=None,
        description="AliExpress product URL",
    )
    product_id: str | None = Field(
        default=None,
        description="AliExpress numeric product ID",
    )

    @model_validator(mode="after")
    def validate_source(self) -> "AliExpressImportRequest":
        if bool(self.url) == bool(self.product_id):
            raise ValueError("Provide exactly one of url or product_id")
        return self


class AliExpressImportResponse(BaseModel):
    product: ProductRead
    aliexpress_product_id: str
    imported: bool = Field(description="True when created, False when updated")
    image_count: int
