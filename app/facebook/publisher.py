from dataclasses import dataclass

from app.facebook.client import FacebookGraphClient, FacebookGraphError
from app.services.exceptions import FacebookPublishError


@dataclass(frozen=True)
class FacebookPublishResult:
    page_id: str
    post_id: str
    message_type: str


class FacebookPublisher:
    """Small provider adapter for Page feed and photo publishing."""

    def __init__(self, client: FacebookGraphClient | None = None) -> None:
        self.client = client or FacebookGraphClient()

    async def publish(
        self,
        page_id: str,
        access_token: str,
        text: str,
        *,
        image_url: str | None = None,
        affiliate_url: str | None = None,
    ) -> FacebookPublishResult:
        if image_url:
            caption = text
            if affiliate_url and affiliate_url not in caption:
                caption = f"{caption}\n\n{affiliate_url}"
            try:
                post_id = await self.client.publish_photo(
                    page_id, access_token, image_url=image_url, caption=caption
                )
            except FacebookGraphError as exc:
                raise FacebookPublishError(
                    exc.message,
                    http_status=exc.status_code,
                    ambiguous=exc.status_code >= 500,
                ) from exc
            return FacebookPublishResult(page_id, post_id, "photo")

        try:
            post_id = await self.client.publish_feed(
                page_id, access_token, message=text, link=affiliate_url
            )
        except FacebookGraphError as exc:
            raise FacebookPublishError(
                exc.message,
                http_status=exc.status_code,
                ambiguous=exc.status_code >= 500,
            ) from exc
        return FacebookPublishResult(page_id, post_id, "text")
