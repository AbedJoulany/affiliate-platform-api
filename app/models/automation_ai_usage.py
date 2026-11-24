from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.model_mixins import TimestampMixin, UUIDPrimaryKeyMixin


class AutomationAIUsageReservation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Durable, conservative accounting for one automation provider submission."""

    __tablename__ = "automation_ai_usage_reservations"
    __table_args__ = (
        UniqueConstraint("run_item_id", name="uq_automation_ai_usage_run_item"),
        UniqueConstraint(
            "provider_submission_id",
            name="uq_automation_ai_usage_submission",
        ),
        CheckConstraint(
            "status IN ('reserved', 'submitted', 'settled', 'uncertain', 'released')",
            name="ck_automation_ai_usage_status",
        ),
        CheckConstraint(
            "provider IN ('openai', 'gemini')",
            name="ck_automation_ai_usage_provider",
        ),
        CheckConstraint(
            "status != 'settled' OR usage_complete",
            name="ck_automation_ai_usage_settled_complete",
        ),
        CheckConstraint(
            "NOT usage_complete OR (actual_input_tokens IS NOT NULL AND "
            "actual_output_tokens IS NOT NULL AND actual_total_tokens IS NOT NULL)",
            name="ck_automation_ai_usage_complete_counts",
        ),
        CheckConstraint("reserved_tokens > 0", name="ck_automation_ai_usage_reserved_positive"),
        CheckConstraint(
            "actual_input_tokens IS NULL OR actual_input_tokens >= 0",
            name="ck_automation_ai_usage_input_nonnegative",
        ),
        CheckConstraint(
            "actual_output_tokens IS NULL OR actual_output_tokens >= 0",
            name="ck_automation_ai_usage_output_nonnegative",
        ),
        CheckConstraint(
            "actual_total_tokens IS NULL OR actual_total_tokens >= 0",
            name="ck_automation_ai_usage_total_nonnegative",
        ),
        Index("ix_automation_ai_usage_workspace_day", "workspace_id", "workspace_usage_date"),
        Index("ix_automation_ai_usage_global_day", "global_usage_date"),
        Index("ix_automation_ai_usage_status_created", "status", "created_at"),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False
    )
    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("automation_runs.id", ondelete="RESTRICT"), nullable=False
    )
    run_item_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("automation_run_items.id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider_submission_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(24), nullable=False)
    requested_model: Mapped[str] = mapped_column(String(128), nullable=False)
    actual_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    workspace_usage_date: Mapped[date] = mapped_column(Date, nullable=False)
    global_usage_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="reserved")
    reserved_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    actual_input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usage_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    workspace = relationship("Workspace")
    run = relationship("AutomationRun")
    run_item = relationship("AutomationRunItem")
