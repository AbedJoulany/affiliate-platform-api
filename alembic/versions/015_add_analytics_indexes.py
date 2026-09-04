"""Add analytics query indexes on clicks and conversions

Revision ID: 015
Revises: 014
Create Date: 2026-09-04

Additive indexes only. Does not add workspace_id to clicks or conversions.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "015"
down_revision: str | None = "014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_clicks_affiliate_campaign_id_created_at",
        "clicks",
        ["affiliate_campaign_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_conversions_campaign_id_created_at_status",
        "conversions",
        ["campaign_id", "created_at", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conversions_campaign_id_created_at_status",
        table_name="conversions",
    )
    op.drop_index(
        "ix_clicks_affiliate_campaign_id_created_at",
        table_name="clicks",
    )
