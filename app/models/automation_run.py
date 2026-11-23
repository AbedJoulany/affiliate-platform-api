from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.model_mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.automation_policy import AutomationPolicy
    from app.models.queue import QueueItem
    from app.models.workspace import Workspace


class AutomationRun(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Durable identity and bounded recovery state for one local daily run."""

    __tablename__ = "automation_runs"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "policy_id",
            "local_date",
            name="uq_automation_runs_workspace_policy_local_date",
        ),
        CheckConstraint("policy_revision > 0", name="ck_automation_runs_revision_positive"),
        CheckConstraint(
            "status IN ('claimed', 'running', 'completed', 'completed_with_errors', "
            "'failed', 'missed', 'cancelled', 'needs_operator_review')",
            name="ck_automation_runs_status",
        ),
        CheckConstraint(
            "selected_count >= 0 AND generated_count >= 0 AND queued_count >= 0 "
            "AND skipped_count >= 0 AND failed_count >= 0",
            name="ck_automation_runs_counts_nonnegative",
        ),
        Index("ix_automation_runs_status_lease", "status", "lease_expires_at"),
        Index("ix_automation_runs_scheduled_for", "scheduled_for"),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    policy_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("automation_policies.id", ondelete="CASCADE"),
        nullable=False,
    )
    policy_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="claimed", nullable=False)
    lease_owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    selected_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    generated_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    queued_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)

    workspace: Mapped["Workspace"] = relationship("Workspace")
    policy: Mapped["AutomationPolicy"] = relationship("AutomationPolicy")
    items: Mapped[list["AutomationRunItem"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class AutomationRunItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Per-product checkpoint; generated text permits safe Queue-only recovery."""

    __tablename__ = "automation_run_items"
    __table_args__ = (
        UniqueConstraint("run_id", "product_id", name="uq_automation_run_items_run_product"),
        CheckConstraint(
            "status IN ('selected', 'generating', 'generated', 'queued', 'skipped', "
            "'failed', 'uncertain')",
            name="ck_automation_run_items_status",
        ),
        CheckConstraint(
            "generation_state IN ('not_started', 'started', 'succeeded', 'failed', 'uncertain')",
            name="ck_automation_run_items_generation_state",
        ),
        CheckConstraint(
            "selection_rank > 0", name="ck_automation_run_items_rank_positive"
        ),
        Index("ix_automation_run_items_run_id", "run_id"),
    )

    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("automation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    selection_rank: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="selected", nullable=False)
    generation_state: Mapped[str] = mapped_column(
        String(16), default="not_started", nullable=False
    )
    generation_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    generation_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    generated_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    affiliate_url_snapshot: Mapped[str | None] = mapped_column(String(512), nullable=True)
    queue_item_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("queue_items.id", ondelete="SET NULL"), nullable=True
    )
    queue_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)

    run: Mapped["AutomationRun"] = relationship(back_populates="items")
    queue_item: Mapped["QueueItem | None"] = relationship("QueueItem")
