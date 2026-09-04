"""Add workspace_settings table

Revision ID: 016
Revises: 015
Create Date: 2026-09-04

One row per workspace. Additive table only — no secret columns.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "016"
down_revision: str | None = "015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspace_settings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("ui_language", sa.String(length=8), nullable=False),
        sa.Column("aliexpress_target_currency", sa.String(length=3), nullable=False),
        sa.Column("aliexpress_ship_to_country", sa.String(length=2), nullable=False),
        sa.Column("aliexpress_target_language", sa.String(length=8), nullable=False),
        sa.Column("default_ai_provider", sa.String(length=16), nullable=False),
        sa.Column("default_content_type", sa.String(length=32), nullable=False),
        sa.Column("default_tone", sa.String(length=32), nullable=False),
        sa.Column("default_content_language", sa.String(length=8), nullable=False),
        sa.Column("default_content_length", sa.String(length=16), nullable=False),
        sa.Column("discovery_default_mode", sa.String(length=32), nullable=False),
        sa.Column("discovery_page_size", sa.Integer(), nullable=False),
        sa.Column("default_telegram_channel_id", sa.UUID(), nullable=True),
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
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["default_telegram_channel_id"],
            ["telegram_channels.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", name="uq_workspace_settings_workspace_id"),
    )


def downgrade() -> None:
    op.drop_table("workspace_settings")
