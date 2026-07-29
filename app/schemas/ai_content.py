from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, model_validator

from app.core.enums import (
    AIProviderType,
    ContentLanguage,
    ContentLength,
    ContentType,
    ToneProfile,
)

ALLOWED_INSTRUCTION_MODIFIERS = frozenset(
    {
        "add_emojis",
        "strengthen_cta",
        "shorten",
        "increase_urgency",
        "improve_seo",
    }
)


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
    content_type: ContentType = Field(
        default=ContentType.TELEGRAM,
        description="Target content platform / format",
    )
    tone: ToneProfile = Field(
        default=ToneProfile.PERSUASIVE,
        description="Tone / prompt profile",
    )
    language: ContentLanguage = Field(
        default=ContentLanguage.AR,
        description="Output language",
    )
    length: ContentLength = Field(
        default=ContentLength.MEDIUM,
        description="Target content length band",
    )
    instruction_modifiers: list[str] = Field(
        default_factory=list,
        description="Optional prompt tuning modifiers from the AI Suggestions panel",
    )

    @model_validator(mode="after")
    def validate_source(self) -> "GenerateContentRequest":
        has_product_id = self.product_id is not None
        has_url = self.url is not None
        if has_product_id == has_url:
            raise ValueError("Provide exactly one of product_id or url")
        unknown = [item for item in self.instruction_modifiers if item not in ALLOWED_INSTRUCTION_MODIFIERS]
        if unknown:
            raise ValueError(f"Unsupported instruction_modifiers: {', '.join(unknown)}")
        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for item in self.instruction_modifiers:
            if item not in seen:
                seen.add(item)
                unique.append(item)
        self.instruction_modifiers = unique
        return self


class GenerateContentResponse(BaseModel):
    product_id: UUID | None = None
    source_url: str | None = None
    provider: AIProviderType
    content: str = Field(description="Generated marketing content")
    content_type: ContentType = ContentType.TELEGRAM
    tone: ToneProfile = ToneProfile.PERSUASIVE
    language: ContentLanguage = ContentLanguage.AR
    length: ContentLength = ContentLength.MEDIUM
