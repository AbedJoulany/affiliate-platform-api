from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import BotPermissionStatus
from app.core.model_mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.workspace import Workspace


class TelegramChannel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "telegram_channels"

    telegram_channel_id: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
    )
    workspace_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    bot_permission_status: Mapped[BotPermissionStatus] = mapped_column(
        Enum(BotPermissionStatus, name="bot_permission_status", native_enum=False),
        default=BotPermissionStatus.UNKNOWN,
        nullable=False,
    )
    can_post_messages: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_edit_messages: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    can_delete_messages: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    permissions_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    permission_detail: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        foreign_keys=[workspace_id],
    )
