from app.ai.base import AIProvider
from app.ai.gemini_provider import GeminiProvider
from app.ai.openai_provider import OpenAIProvider
from app.core.config import get_settings
from app.core.enums import AIProviderType
from app.services.exceptions import ValidationError

settings = get_settings()

_PROVIDERS: dict[AIProviderType, type[AIProvider]] = {
    AIProviderType.OPENAI: OpenAIProvider,
    AIProviderType.GEMINI: GeminiProvider,
}


def get_ai_provider(provider: AIProviderType | None = None) -> AIProvider:
    provider_type = provider or settings.ai_default_provider
    provider_class = _PROVIDERS.get(provider_type)
    if not provider_class:
        raise ValidationError(f"Unsupported AI provider: {provider_type}")

    instance = provider_class()
    if not instance.is_configured:
        raise ValidationError(f"{provider_type.value} API key is not configured")

    return instance
