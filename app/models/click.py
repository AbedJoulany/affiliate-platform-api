from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.model_mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.affiliate import AffiliateCampaign


def generate_click_id() -> str:
    """Return a public, URL-safe token compatible with Conversion.click_id."""
    return uuid4().hex


class Click(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "clicks"

    affiliate_campaign_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("affiliate_campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    click_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
        default=generate_click_id,
    )

    affiliate_campaign: Mapped["AffiliateCampaign"] = relationship(
        "AffiliateCampaign",
        back_populates="clicks",
    )
