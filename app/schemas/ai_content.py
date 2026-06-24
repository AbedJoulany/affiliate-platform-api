from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, model_validator

from app.core.enums import AIProviderType


class GenerateContentRequest(BaseModel):
    product_id: UUID | None = Field(
        default=None,
        description="Generate content from a product stored in the database",
    )
    url: HttpUrl | str | None = Field(
        default=None,
        description="Generate content by fetching product metadata from a URL",
    )
    provider: AIProviderType | None = Field(
        default=None,
        description="Override the default AI provider (openai or gemini)",
    )

    @model_validator(mode="after")
    def validate_source(self) -> "GenerateContentRequest":
        has_product_id = self.product_id is not None
        has_url = self.url is not None
        if has_product_id == has_url:
            raise ValueError("Provide exactly one of product_id or url")
        return self


class GenerateContentResponse(BaseModel):
    product_id: UUID | None = None
    source_url: str | None = None
    provider: AIProviderType
    content: str = Field(description="Arabic marketing content")
