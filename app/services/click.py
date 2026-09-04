from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.click import Click, generate_click_id
from app.repositories.affiliate import AffiliateCampaignRepository
from app.repositories.click import ClickRepository
from app.services.exceptions import NotFoundError, ValidationError


def is_safe_redirect_url(url: str) -> bool:
    """Return True when ``url`` is an absolute http(s) destination."""
    if not url or any(ord(char) < 32 for char in url):
        return False
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        return False
    if not parsed.netloc:
        return False
    if parsed.username is not None or parsed.password is not None:
        return False
    return True


class ClickService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.click_repo = ClickRepository(session)
        self.link_repo = AffiliateCampaignRepository(session)

    async def record_public_click(self, affiliate_campaign_id: UUID) -> tuple[Click, str]:
        link = await self.link_repo.get_by_id(affiliate_campaign_id)
        if link is None:
            raise NotFoundError("Affiliate campaign not found")

        destination = (link.tracking_link or "").strip()
        if not destination:
            raise ValidationError("Tracking link is missing")
        if not is_safe_redirect_url(destination):
            raise ValidationError("Tracking link is not a valid destination")

        click = Click(
            affiliate_campaign_id=link.id,
            click_id=generate_click_id(),
        )
        await self.click_repo.create(click)
        return click, destination
