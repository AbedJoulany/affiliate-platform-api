from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import ConversionStatus
from app.core.model_mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.affiliate import Affiliate
    from app.models.campaign import Campaign


class Conversion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "conversions"

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
    external_order_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    commission: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    status: Mapped[ConversionStatus] = mapped_column(
        Enum(ConversionStatus, name="conversion_status", native_enum=False),
        default=ConversionStatus.PENDING,
        nullable=False,
    )
    click_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    affiliate: Mapped["Affiliate"] = relationship("Affiliate", back_populates="conversions")
    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="conversions")
