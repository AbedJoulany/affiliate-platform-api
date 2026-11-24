import httpx

from app.ai.base import AIProvider
from app.ai.retry import AI_MAX_ATTEMPTS, execute_with_retries
from app.ai.usage import ProviderGeneration, parse_gemini_usage
from app.core.config import get_settings
from app.services.exceptions import AIProviderError

settings = get_settings()


class GeminiProvider(AIProvider):
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.api_key = api_key or settings.gemini_api_key
        self.model = model or settings.gemini_model
        self.base_url = (base_url or settings.gemini_api_base_url).rstrip("/")

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def generate_content(self, prompt: str, *, allow_retries: bool = True) -> str:
        if not self.is_configured:
            raise AIProviderError("Gemini API key is not configured")

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "You are an expert Arabic affiliate marketing copywriter. "
                                "Write persuasive, natural Arabic content suitable for "
                                "Telegram channels.\n\n"
                                f"{prompt}"
                            )
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
            },
        }

        # Path only — never log the full URL (API key is a query param).
        url = f"{self.base_url}/models/{self.model}:generateContent"
        params = {"key": self.api_key}

        async def _request_once() -> dict:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, params=params, json=payload)
                response.raise_for_status()
                return response.json()

        try:
            data = await execute_with_retries(
                _request_once,
                provider=self.name,
                max_attempts=AI_MAX_ATTEMPTS if allow_retries else 1,
            )
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code in {401, 403}:
                category = "provider_authentication_error"
                detail = "Gemini provider authentication failed"
            elif status_code == 429:
                category = "provider_rate_limited"
                detail = "Gemini provider rate limit exceeded"
            elif status_code >= 500:
                category = "provider_unavailable"
                detail = "Gemini provider unavailable"
            else:
                category = "provider_request_error"
                detail = "Gemini provider request failed"
            raise AIProviderError(detail, category=category) from exc
        except httpx.HTTPError as exc:
            raise AIProviderError(
                "Gemini provider network request failed",
                category="provider_unavailable",
            ) from exc

        try:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError("Gemini returned an unexpected response format") from exc

    async def generate_content_with_usage(
        self,
        prompt: str,
        *,
        max_output_tokens: int,
    ) -> ProviderGeneration:
        """Single-attempt GenerateContent request with usage metadata."""
        if not self.is_configured:
            raise AIProviderError("Gemini API key is not configured")
        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": (
                                "You are an expert Arabic affiliate marketing copywriter. "
                                "Write persuasive, natural Arabic content suitable for "
                                "Telegram channels.\n\n"
                                f"{prompt}"
                            )
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": max_output_tokens,
            },
        }
        url = f"{self.base_url}/models/{self.model}:generateContent"
        headers = {"x-goog-api-key": self.api_key}

        async def _request_once() -> dict:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                return response.json()

        try:
            data = await execute_with_retries(
                _request_once,
                provider=self.name,
                max_attempts=1,
            )
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            category = (
                "provider_authentication_error"
                if status_code in {401, 403}
                else "provider_rate_limited"
                if status_code == 429
                else "provider_unavailable"
                if status_code >= 500
                else "provider_request_error"
            )
            detail = {
                "provider_authentication_error": "Gemini provider authentication failed",
                "provider_rate_limited": "Gemini provider rate limit exceeded",
                "provider_unavailable": "Gemini provider unavailable",
                "provider_request_error": "Gemini provider request failed",
            }[category]
            raise AIProviderError(detail, category=category) from None
        except httpx.HTTPError:
            raise AIProviderError(
                "Gemini provider network request failed",
                category="provider_unavailable",
            ) from None

        try:
            content = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, TypeError, AttributeError):
            raise AIProviderError("Gemini returned an unexpected response format") from None
        return ProviderGeneration(
            content=content,
            usage=parse_gemini_usage(data, self.model),
        )
