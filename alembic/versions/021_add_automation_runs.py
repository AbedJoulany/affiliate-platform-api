"""Add durable automation run and per-product checkpoints.

Unattended execution remains disabled. These tables record logical daily run
identity and support conservative recovery without creating a second Queue.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "021"
down_revision: str | None = "020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "automation_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("policy_id", sa.UUID(), nullable=False),
        sa.Column("policy_revision", sa.Integer(), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="claimed", nullable=False),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("selected_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("generated_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("queued_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("skipped_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_category", sa.String(length=100), nullable=True),
        sa.Column("error_summary", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["policy_id"], ["automation_policies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id", "policy_id", "local_date",
            name="uq_automation_runs_workspace_policy_local_date",
        ),
        sa.CheckConstraint("policy_revision > 0", name="ck_automation_runs_revision_positive"),
        sa.CheckConstraint(
            "status IN ('claimed', 'running', 'completed', 'completed_with_errors', "
            "'failed', 'missed', 'cancelled', 'needs_operator_review')",
            name="ck_automation_runs_status",
        ),
        sa.CheckConstraint(
            "selected_count >= 0 AND generated_count >= 0 AND queued_count >= 0 "
            "AND skipped_count >= 0 AND failed_count >= 0",
            name="ck_automation_runs_counts_nonnegative",
        ),
    )
    op.create_index("ix_automation_runs_workspace_id", "automation_runs", ["workspace_id"])
    op.create_index(
        "ix_automation_runs_status_lease",
        "automation_runs",
        ["status", "lease_expires_at"],
    )
    op.create_index("ix_automation_runs_scheduled_for", "automation_runs", ["scheduled_for"])

    op.create_table(
        "automation_run_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=True),
        sa.Column("selection_rank", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="selected", nullable=False),
        sa.Column(
            "generation_state",
            sa.String(length=16),
            server_default="not_started",
            nullable=False,
        ),
        sa.Column("generation_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("generation_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("generated_content", sa.Text(), nullable=True),
        sa.Column("affiliate_url_snapshot", sa.String(length=512), nullable=True),
        sa.Column("queue_item_id", sa.UUID(), nullable=True),
        sa.Column("queue_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_category", sa.String(length=100), nullable=True),
        sa.Column("failure_summary", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["automation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["queue_item_id"], ["queue_items.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "product_id", name="uq_automation_run_items_run_product"),
        sa.CheckConstraint(
            "status IN ('selected', 'generating', 'generated', 'queued', "
            "'skipped', 'failed', 'uncertain')",
            name="ck_automation_run_items_status",
        ),
        sa.CheckConstraint(
            "generation_state IN ('not_started', 'started', 'succeeded', 'failed', 'uncertain')",
            name="ck_automation_run_items_generation_state",
        ),
        sa.CheckConstraint("selection_rank > 0", name="ck_automation_run_items_rank_positive"),
    )
    op.create_index("ix_automation_run_items_run_id", "automation_run_items", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_automation_run_items_run_id", table_name="automation_run_items")
    op.drop_table("automation_run_items")
    op.drop_index("ix_automation_runs_scheduled_for", table_name="automation_runs")
    op.drop_index("ix_automation_runs_status_lease", table_name="automation_runs")
    op.drop_index("ix_automation_runs_workspace_id", table_name="automation_runs")
    op.drop_table("automation_runs")
