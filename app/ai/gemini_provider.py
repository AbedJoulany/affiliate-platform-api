import httpx

from app.ai.base import AIProvider
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

    async def generate_content(self, prompt: str) -> str:
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

        url = f"{self.base_url}/models/{self.model}:generateContent"
        params = {"key": self.api_key}

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(url, params=params, json=payload)
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as exc:
                detail = exc.response.text
                raise AIProviderError(f"Gemini request failed: {detail}") from exc
            except httpx.HTTPError as exc:
                raise AIProviderError(f"Gemini request failed: {exc}") from exc

        try:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError("Gemini returned an unexpected response format") from exc
