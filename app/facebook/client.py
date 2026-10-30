from dataclasses import dataclass

import httpx

from app.core.config import Settings, get_settings


class FacebookGraphError(Exception):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


@dataclass(frozen=True)
class FacebookPageIdentity:
    page_id: str
    name: str


class FacebookGraphClient:
    def __init__(
        self,
        settings: Settings | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.http_client = http_client

    async def validate_page(self, page_id: str, access_token: str) -> FacebookPageIdentity:
        if not page_id.isdigit():
            raise FacebookGraphError("Facebook Page ID must contain only digits", status_code=422)
        url = (
            f"{self.settings.facebook_graph_api_base_url.rstrip('/')}/"
            f"{self.settings.facebook_graph_api_version.strip('/')}/{page_id}"
        )
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"fields": "id,name"}
        try:
            if self.http_client is not None:
                response = await self.http_client.get(url, params=params, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(url, params=params, headers=headers)
        except httpx.TimeoutException as exc:
            raise FacebookGraphError(
                "Facebook Graph API request timed out", status_code=504
            ) from exc
        except httpx.RequestError as exc:
            raise FacebookGraphError("Facebook Graph API request failed", status_code=502) from exc

        if response.status_code == 429:
            raise FacebookGraphError("Facebook Graph API rate limit reached", status_code=429)
        if response.status_code in (401, 403):
            raise FacebookGraphError(
                "Facebook credentials are invalid or lack access to this Page",
                status_code=422,
            )
        if response.status_code == 404:
            raise FacebookGraphError(
                "Facebook Page was not found or is not accessible", status_code=422
            )
        if response.status_code >= 400:
            raise FacebookGraphError("Facebook Page validation failed", status_code=502)

        try:
            payload = response.json()
            resolved_id = str(payload["id"])
            name = str(payload["name"]).strip()
        except (ValueError, KeyError, TypeError) as exc:
            raise FacebookGraphError(
                "Facebook returned an invalid Page response", status_code=502
            ) from exc
        if not resolved_id.isdigit() or not name:
            raise FacebookGraphError("Facebook returned incomplete Page metadata", status_code=502)
        if resolved_id != page_id:
            raise FacebookGraphError("Facebook returned a different Page ID", status_code=502)
        return FacebookPageIdentity(page_id=resolved_id, name=name[:255])
