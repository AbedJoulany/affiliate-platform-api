"""Add durable per-submission automation AI usage reservations."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "022"
down_revision: str | None = "021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "automation_ai_usage_reservations",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("run_item_id", sa.UUID(), nullable=False),
        sa.Column("provider_submission_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=24), nullable=False),
        sa.Column("requested_model", sa.String(length=128), nullable=False),
        sa.Column("actual_model", sa.String(length=128), nullable=True),
        sa.Column("workspace_usage_date", sa.Date(), nullable=False),
        sa.Column("global_usage_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="reserved", nullable=False),
        sa.Column("reserved_tokens", sa.Integer(), nullable=False),
        sa.Column("actual_input_tokens", sa.Integer(), nullable=True),
        sa.Column("actual_output_tokens", sa.Integer(), nullable=True),
        sa.Column("actual_total_tokens", sa.Integer(), nullable=True),
        sa.Column("usage_complete", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["run_id"], ["automation_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["run_item_id"], ["automation_run_items.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_item_id", name="uq_automation_ai_usage_run_item"),
        sa.UniqueConstraint("provider_submission_id", name="uq_automation_ai_usage_submission"),
        sa.CheckConstraint(
            "status IN ('reserved', 'submitted', 'settled', 'uncertain', 'released')",
            name="ck_automation_ai_usage_status",
        ),
        sa.CheckConstraint(
            "provider IN ('openai', 'gemini')",
            name="ck_automation_ai_usage_provider",
        ),
        sa.CheckConstraint(
            "status != 'settled' OR usage_complete",
            name="ck_automation_ai_usage_settled_complete",
        ),
        sa.CheckConstraint(
            "NOT usage_complete OR (actual_input_tokens IS NOT NULL AND "
            "actual_output_tokens IS NOT NULL AND actual_total_tokens IS NOT NULL)",
            name="ck_automation_ai_usage_complete_counts",
        ),
        sa.CheckConstraint("reserved_tokens > 0", name="ck_automation_ai_usage_reserved_positive"),
        sa.CheckConstraint(
            "actual_input_tokens IS NULL OR actual_input_tokens >= 0",
            name="ck_automation_ai_usage_input_nonnegative",
        ),
        sa.CheckConstraint(
            "actual_output_tokens IS NULL OR actual_output_tokens >= 0",
            name="ck_automation_ai_usage_output_nonnegative",
        ),
        sa.CheckConstraint(
            "actual_total_tokens IS NULL OR actual_total_tokens >= 0",
            name="ck_automation_ai_usage_total_nonnegative",
        ),
    )
    op.create_index(
        "ix_automation_ai_usage_workspace_day",
        "automation_ai_usage_reservations",
        ["workspace_id", "workspace_usage_date"],
    )
    op.create_index(
        "ix_automation_ai_usage_global_day",
        "automation_ai_usage_reservations",
        ["global_usage_date"],
    )
    op.create_index(
        "ix_automation_ai_usage_status_created",
        "automation_ai_usage_reservations",
        ["status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_automation_ai_usage_status_created",
        table_name="automation_ai_usage_reservations",
    )
    op.drop_index(
        "ix_automation_ai_usage_global_day",
        table_name="automation_ai_usage_reservations",
    )
    op.drop_index(
        "ix_automation_ai_usage_workspace_day", table_name="automation_ai_usage_reservations"
    )
    op.drop_table("automation_ai_usage_reservations")
