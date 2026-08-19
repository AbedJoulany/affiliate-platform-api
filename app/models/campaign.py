from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import CampaignStatus
from app.core.model_mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.auth.models import User
    from app.models.affiliate import AffiliateCampaign
    from app.models.conversion import Conversion
    from app.models.workspace import Workspace


class Campaign(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "campaigns"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    advertiser_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    workspace_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[CampaignStatus] = mapped_column(
        Enum(CampaignStatus, name="campaign_status", native_enum=False),
        default=CampaignStatus.DRAFT,
        nullable=False,
    )
    payout_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    landing_url: Mapped[str] = mapped_column(String(512), nullable=False)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    advertiser: Mapped["User | None"] = relationship("User")
    workspace: Mapped["Workspace | None"] = relationship(
        "Workspace",
        foreign_keys=[workspace_id],
    )
    affiliate_links: Mapped[list["AffiliateCampaign"]] = relationship(
        "AffiliateCampaign",
        back_populates="campaign",
        cascade="all, delete-orphan",
    )
    conversions: Mapped[list["Conversion"]] = relationship(
        "Conversion",
        back_populates="campaign",
    )
