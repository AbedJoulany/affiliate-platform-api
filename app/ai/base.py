from abc import ABC, abstractmethod

from app.ai.usage import ProviderGeneration
from app.services.exceptions import AIProviderError


class AIProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    async def generate_content(self, prompt: str, *, allow_retries: bool = True) -> str:
        raise NotImplementedError

    async def generate_content_with_usage(
        self,
        prompt: str,
        *,
        max_output_tokens: int,
    ) -> ProviderGeneration:
        """Automation-only boundary; providers must opt in with trustworthy usage."""
        raise AIProviderError(
            "Selected AI provider does not support usage accounting",
            category="provider_usage_unsupported",
        )

    @property
    def is_configured(self) -> bool:
        return True
