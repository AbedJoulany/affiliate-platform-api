from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.model_mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.channel import TelegramChannel
    from app.models.workspace import Workspace


class WorkspaceSettings(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """One settings row per workspace. Deleted with the workspace."""

    __tablename__ = "workspace_settings"

    workspace_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    ui_language: Mapped[str] = mapped_column(String(8), default="ar", nullable=False)
    aliexpress_target_currency: Mapped[str] = mapped_column(
        String(3), default="USD", nullable=False
    )
    aliexpress_ship_to_country: Mapped[str] = mapped_column(
        String(2), default="IL", nullable=False
    )
    aliexpress_target_language: Mapped[str] = mapped_column(
        String(8), default="EN", nullable=False
    )
    default_ai_provider: Mapped[str] = mapped_column(
        String(16), default="openai", nullable=False
    )
    default_content_type: Mapped[str] = mapped_column(
        String(32), default="telegram", nullable=False
    )
    default_tone: Mapped[str] = mapped_column(
        String(32), default="persuasive", nullable=False
    )
    default_content_language: Mapped[str] = mapped_column(
        String(8), default="ar", nullable=False
    )
    default_content_length: Mapped[str] = mapped_column(
        String(16), default="medium", nullable=False
    )
    discovery_default_mode: Mapped[str] = mapped_column(
        String(32), default="general", nullable=False
    )
    discovery_page_size: Mapped[int] = mapped_column(
        Integer, default=20, nullable=False
    )
    default_telegram_channel_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("telegram_channels.id", ondelete="SET NULL"),
        nullable=True,
    )

    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        back_populates="settings",
    )
    default_telegram_channel: Mapped["TelegramChannel | None"] = relationship(
        "TelegramChannel",
        foreign_keys=[default_telegram_channel_id],
    )
