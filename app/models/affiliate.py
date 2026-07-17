from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import AffiliateStatus
from app.core.model_mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.auth.models import User
    from app.models.campaign import Campaign
    from app.models.conversion import Conversion


class Affiliate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "affiliates"

    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website: Mapped[str | None] = mapped_column(String(512), nullable=True)
    referral_code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    status: Mapped[AffiliateStatus] = mapped_column(
        Enum(AffiliateStatus, name="affiliate_status", native_enum=False),
        default=AffiliateStatus.PENDING,
        nullable=False,
    )
    commission_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("10.00"),
        nullable=False,
    )
    payout_details: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="affiliate_profile")
    campaign_links: Mapped[list["AffiliateCampaign"]] = relationship(
        "AffiliateCampaign",
        back_populates="affiliate",
        cascade="all, delete-orphan",
    )
    conversions: Mapped[list["Conversion"]] = relationship(
        "Conversion",
        back_populates="affiliate",
    )


class AffiliateCampaign(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "affiliate_campaigns"
    __table_args__ = (
        UniqueConstraint("affiliate_id", "campaign_id", name="uq_affiliate_campaign"),
    )

    affiliate_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("affiliates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    campaign_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tracking_link: Mapped[str] = mapped_column(String(512), nullable=False)

    affiliate: Mapped["Affiliate"] = relationship("Affiliate", back_populates="campaign_links")
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="affiliate_links")
