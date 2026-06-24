from pydantic import BaseModel, Field, HttpUrl, model_validator

from app.schemas.product import ProductRead


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
