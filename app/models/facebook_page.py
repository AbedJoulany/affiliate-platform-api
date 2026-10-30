from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.enums import FacebookPageValidationStatus
from app.core.model_mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.workspace import Workspace


class FacebookPage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "facebook_pages"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "facebook_page_id",
            name="uq_facebook_pages_workspace_page_id",
        ),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    facebook_page_id: Mapped[str] = mapped_column(String(64), nullable=False)
    page_name: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_access_token: Mapped[str] = mapped_column(Text, nullable=False)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    validation_status: Mapped[FacebookPageValidationStatus] = mapped_column(
        Enum(
            FacebookPageValidationStatus,
            name="facebook_page_validation_status",
            native_enum=False,
        ),
        default=FacebookPageValidationStatus.UNKNOWN,
        nullable=False,
    )
    last_validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(String(512), nullable=True)

    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        back_populates="facebook_pages",
    )
