"""Add clicks table for affiliate-link tracking

Revision ID: 014
Revises: 013
Create Date: 2026-08-23

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "014"
down_revision: str | None = "013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "clicks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("affiliate_campaign_id", sa.UUID(), nullable=False),
        sa.Column("click_id", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["affiliate_campaign_id"],
            ["affiliate_campaigns.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_clicks_affiliate_campaign_id"),
        "clicks",
        ["affiliate_campaign_id"],
        unique=False,
    )
    op.create_index(op.f("ix_clicks_click_id"), "clicks", ["click_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_clicks_click_id"), table_name="clicks")
    op.drop_index(op.f("ix_clicks_affiliate_campaign_id"), table_name="clicks")
    op.drop_table("clicks")
