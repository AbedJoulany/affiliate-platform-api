from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import QueueStatus
from app.core.model_mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.channel import TelegramChannel
    from app.models.product import Product


class QueueItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "queue_items"

    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[QueueStatus] = mapped_column(
        Enum(QueueStatus, name="queue_status", native_enum=False),
        default=QueueStatus.DRAFT,
        nullable=False,
        index=True,
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    channel_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("telegram_channels.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    product_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    button_text: Mapped[str | None] = mapped_column(String(128), nullable=True)
    button_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    channel: Mapped["TelegramChannel | None"] = relationship("TelegramChannel")
    product: Mapped["Product | None"] = relationship("Product")
