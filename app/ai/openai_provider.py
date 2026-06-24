import httpx

from app.ai.base import AIProvider
from app.core.config import get_settings
from app.services.exceptions import AIProviderError

settings = get_settings()


class OpenAIProvider(AIProvider):
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.openai_model
        self.base_url = (base_url or settings.openai_api_base_url).rstrip("/")

    @property
    def name(self) -> str:
        return "openai"

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    async def generate_content(self, prompt: str) -> str:
        if not self.is_configured:
            raise AIProviderError("OpenAI API key is not configured")

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an expert Arabic affiliate marketing copywriter. "
                        "Write persuasive, natural Arabic content suitable for Telegram channels."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as exc:
                detail = exc.response.text
                raise AIProviderError(f"OpenAI request failed: {detail}") from exc
            except httpx.HTTPError as exc:
                raise AIProviderError(f"OpenAI request failed: {exc}") from exc

        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError("OpenAI returned an unexpected response format") from exc
