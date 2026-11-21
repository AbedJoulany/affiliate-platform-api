from datetime import time
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, String, Time
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import AutomationFrequency, AutomationProvider
from app.core.model_mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.channel import TelegramChannel
    from app.models.facebook_page import FacebookPage
    from app.models.workspace import Workspace


class AutomationPolicy(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One saved automation configuration per workspace.

    This table stores operator intent only.  It is deliberately not consumed by
    a worker in Phase 5B; execution availability is computed by the service and
    remains disabled until a later, explicitly activated phase.
    """

    __tablename__ = "automation_policies"
    __table_args__ = (
        CheckConstraint("revision > 0", name="ck_automation_policies_revision_positive"),
        CheckConstraint(
            "products_per_run BETWEEN 1 AND 50",
            name="ck_automation_policies_products_per_run",
        ),
        CheckConstraint(
            "posts_per_day BETWEEN 1 AND 10",
            name="ck_automation_policies_posts_per_day",
        ),
        CheckConstraint(
            "min_price IS NULL OR min_price >= 0",
            name="ck_automation_policies_min_price_nonnegative",
        ),
        CheckConstraint(
            "max_price IS NULL OR max_price >= 0",
            name="ck_automation_policies_max_price_nonnegative",
        ),
        CheckConstraint(
            "min_price IS NULL OR max_price IS NULL OR min_price <= max_price",
            name="ck_automation_policies_price_range",
        ),
        CheckConstraint(
            "min_rating IS NULL OR min_rating BETWEEN 0 AND 5",
            name="ck_automation_policies_rating_range",
        ),
        CheckConstraint(
            "min_orders IS NULL OR min_orders >= 0",
            name="ck_automation_policies_orders_nonnegative",
        ),
        CheckConstraint(
            "min_discount IS NULL OR min_discount BETWEEN 0 AND 100",
            name="ck_automation_policies_discount_range",
        ),
        CheckConstraint(
            "min_commission IS NULL OR min_commission BETWEEN 0 AND 100",
            name="ck_automation_policies_min_commission_range",
        ),
        CheckConstraint(
            "max_commission IS NULL OR max_commission BETWEEN 0 AND 100",
            name="ck_automation_policies_max_commission_range",
        ),
        CheckConstraint(
            "min_commission IS NULL OR max_commission IS NULL OR "
            "min_commission <= max_commission",
            name="ck_automation_policies_commission_range",
        ),
        CheckConstraint(
            "provider IN ('telegram', 'facebook')",
            name="ck_automation_policies_provider",
        ),
        CheckConstraint(
            "frequency = 'daily'",
            name="ck_automation_policies_frequency",
        ),
        CheckConstraint(
            "(provider = 'telegram' AND facebook_page_id IS NULL) OR "
            "(provider = 'facebook' AND telegram_channel_id IS NULL)",
            name="ck_automation_policies_destination_provider",
        ),
        CheckConstraint(
            "ai_provider IS NULL OR ai_provider IN ('openai', 'gemini')",
            name="ck_automation_policies_ai_provider",
        ),
        CheckConstraint(
            "content_language IS NULL OR content_language IN ('ar', 'en', 'fr', 'de')",
            name="ck_automation_policies_content_language",
        ),
        CheckConstraint(
            "tone IS NULL OR tone IN "
            "('professional', 'friendly', 'luxury', 'technical', 'urgent', "
            "'minimal', 'persuasive', 'funny')",
            name="ck_automation_policies_tone",
        ),
        CheckConstraint(
            "content_type IS NULL OR content_type IN "
            "('social', 'description', 'telegram', 'facebook', 'blog', 'email')",
            name="ck_automation_policies_content_type",
        ),
        CheckConstraint(
            "content_length IS NULL OR content_length IN ('short', 'medium', 'long')",
            name="ck_automation_policies_content_length",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    provider: Mapped[AutomationProvider] = mapped_column(
        String(16), default=AutomationProvider.TELEGRAM.value, nullable=False
    )
    telegram_channel_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("telegram_channels.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    facebook_page_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("facebook_pages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    keywords: Mapped[str | None] = mapped_column(String(255), nullable=True)
    min_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    max_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    min_rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2), nullable=True)
    min_orders: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_discount: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    min_commission: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    max_commission: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)

    products_per_run: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    posts_per_day: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    frequency: Mapped[AutomationFrequency] = mapped_column(
        String(16), default=AutomationFrequency.DAILY.value, nullable=False
    )
    preferred_time_local: Mapped[time] = mapped_column(
        Time(timezone=False), default=time(hour=9, minute=0), nullable=False
    )

    # Null means inherit the corresponding workspace setting.  Phase 5B only
    # stores these overrides; it never invokes the AI service.
    ai_provider: Mapped[str | None] = mapped_column(String(16), nullable=True)
    content_language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    tone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    content_length: Mapped[str | None] = mapped_column(String(16), nullable=True)

    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        back_populates="automation_policy",
    )
    telegram_channel: Mapped["TelegramChannel | None"] = relationship(
        "TelegramChannel",
        foreign_keys=[telegram_channel_id],
    )
    facebook_page: Mapped["FacebookPage | None"] = relationship(
        "FacebookPage",
        foreign_keys=[facebook_page_id],
    )
