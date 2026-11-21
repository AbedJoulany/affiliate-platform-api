"""Add one workspace-scoped automation policy configuration.

The table stores configuration intent only.  It does not add a worker, queue,
provider call, or automation run history.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "020"
down_revision: str | None = "019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "automation_policies",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("provider", sa.String(length=16), server_default="telegram", nullable=False),
        sa.Column("telegram_channel_id", sa.UUID(), nullable=True),
        sa.Column("facebook_page_id", sa.UUID(), nullable=True),
        sa.Column("keywords", sa.String(length=255), nullable=True),
        sa.Column("min_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("max_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("min_rating", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("min_orders", sa.Integer(), nullable=True),
        sa.Column("min_discount", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("min_commission", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("max_commission", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("products_per_run", sa.Integer(), server_default="5", nullable=False),
        sa.Column("posts_per_day", sa.Integer(), server_default="1", nullable=False),
        sa.Column("frequency", sa.String(length=16), server_default="daily", nullable=False),
        sa.Column(
            "preferred_time_local",
            sa.Time(timezone=False),
            server_default="09:00:00",
            nullable=False,
        ),
        sa.Column("ai_provider", sa.String(length=16), nullable=True),
        sa.Column("content_language", sa.String(length=8), nullable=True),
        sa.Column("tone", sa.String(length=32), nullable=True),
        sa.Column("content_type", sa.String(length=32), nullable=True),
        sa.Column("content_length", sa.String(length=16), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["telegram_channel_id"],
            ["telegram_channels.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["facebook_page_id"],
            ["facebook_pages.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", name="uq_automation_policies_workspace_id"),
        sa.CheckConstraint(
            "revision > 0",
            name="ck_automation_policies_revision_positive",
        ),
        sa.CheckConstraint(
            "products_per_run BETWEEN 1 AND 50",
            name="ck_automation_policies_products_per_run",
        ),
        sa.CheckConstraint(
            "posts_per_day BETWEEN 1 AND 10",
            name="ck_automation_policies_posts_per_day",
        ),
        sa.CheckConstraint(
            "min_price IS NULL OR min_price >= 0",
            name="ck_automation_policies_min_price_nonnegative",
        ),
        sa.CheckConstraint(
            "max_price IS NULL OR max_price >= 0",
            name="ck_automation_policies_max_price_nonnegative",
        ),
        sa.CheckConstraint(
            "min_price IS NULL OR max_price IS NULL OR min_price <= max_price",
            name="ck_automation_policies_price_range",
        ),
        sa.CheckConstraint(
            "min_rating IS NULL OR min_rating BETWEEN 0 AND 5",
            name="ck_automation_policies_rating_range",
        ),
        sa.CheckConstraint(
            "min_orders IS NULL OR min_orders >= 0",
            name="ck_automation_policies_orders_nonnegative",
        ),
        sa.CheckConstraint(
            "min_discount IS NULL OR min_discount BETWEEN 0 AND 100",
            name="ck_automation_policies_discount_range",
        ),
        sa.CheckConstraint(
            "min_commission IS NULL OR min_commission BETWEEN 0 AND 100",
            name="ck_automation_policies_min_commission_range",
        ),
        sa.CheckConstraint(
            "max_commission IS NULL OR max_commission BETWEEN 0 AND 100",
            name="ck_automation_policies_max_commission_range",
        ),
        sa.CheckConstraint(
            "min_commission IS NULL OR max_commission IS NULL OR "
            "min_commission <= max_commission",
            name="ck_automation_policies_commission_range",
        ),
        sa.CheckConstraint(
            "provider IN ('telegram', 'facebook')",
            name="ck_automation_policies_provider",
        ),
        sa.CheckConstraint(
            "frequency = 'daily'",
            name="ck_automation_policies_frequency",
        ),
        sa.CheckConstraint(
            "(provider = 'telegram' AND facebook_page_id IS NULL) OR "
            "(provider = 'facebook' AND telegram_channel_id IS NULL)",
            name="ck_automation_policies_destination_provider",
        ),
        sa.CheckConstraint(
            "ai_provider IS NULL OR ai_provider IN ('openai', 'gemini')",
            name="ck_automation_policies_ai_provider",
        ),
        sa.CheckConstraint(
            "content_language IS NULL OR content_language IN ('ar', 'en', 'fr', 'de')",
            name="ck_automation_policies_content_language",
        ),
        sa.CheckConstraint(
            "tone IS NULL OR tone IN "
            "('professional', 'friendly', 'luxury', 'technical', 'urgent', "
            "'minimal', 'persuasive', 'funny')",
            name="ck_automation_policies_tone",
        ),
        sa.CheckConstraint(
            "content_type IS NULL OR content_type IN "
            "('social', 'description', 'telegram', 'facebook', 'blog', 'email')",
            name="ck_automation_policies_content_type",
        ),
        sa.CheckConstraint(
            "content_length IS NULL OR content_length IN ('short', 'medium', 'long')",
            name="ck_automation_policies_content_length",
        ),
    )
    op.create_index(
        "ix_automation_policies_telegram_channel_id",
        "automation_policies",
        ["telegram_channel_id"],
        unique=False,
    )
    op.create_index(
        "ix_automation_policies_facebook_page_id",
        "automation_policies",
        ["facebook_page_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_automation_policies_facebook_page_id",
        table_name="automation_policies",
    )
    op.drop_index(
        "ix_automation_policies_telegram_channel_id",
        table_name="automation_policies",
    )
    op.drop_table("automation_policies")
