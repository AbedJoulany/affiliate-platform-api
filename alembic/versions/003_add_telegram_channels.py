"""Add telegram_channels table

Revision ID: 003
Revises: 002
Create Date: 2026-06-05

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "telegram_channels",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("telegram_channel_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column(
            "bot_permission_status",
            sa.Enum(
                "unknown",
                "pending",
                "granted",
                "partial",
                "denied",
                name="bot_permission_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("can_post_messages", sa.Boolean(), nullable=False),
        sa.Column("can_edit_messages", sa.Boolean(), nullable=False),
        sa.Column("can_delete_messages", sa.Boolean(), nullable=False),
        sa.Column("permissions_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("permission_detail", sa.String(length=512), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_telegram_channels_telegram_channel_id"),
        "telegram_channels",
        ["telegram_channel_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_telegram_channels_username"),
        "telegram_channels",
        ["username"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_telegram_channels_username"), table_name="telegram_channels")
    op.drop_index(op.f("ix_telegram_channels_telegram_channel_id"), table_name="telegram_channels")
    op.drop_table("telegram_channels")
