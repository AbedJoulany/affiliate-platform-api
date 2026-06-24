"""Add queue_items table

Revision ID: 004
Revises: 003
Create Date: 2026-06-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "queue_items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "queued",
                "scheduled",
                "published",
                name="queue_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("channel_id", sa.UUID(), nullable=True),
        sa.Column("product_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["channel_id"], ["telegram_channels.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_queue_items_status"), "queue_items", ["status"], unique=False)
    op.create_index(op.f("ix_queue_items_scheduled_at"), "queue_items", ["scheduled_at"], unique=False)
    op.create_index(op.f("ix_queue_items_channel_id"), "queue_items", ["channel_id"], unique=False)
    op.create_index(op.f("ix_queue_items_product_id"), "queue_items", ["product_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_queue_items_product_id"), table_name="queue_items")
    op.drop_index(op.f("ix_queue_items_channel_id"), table_name="queue_items")
    op.drop_index(op.f("ix_queue_items_scheduled_at"), table_name="queue_items")
    op.drop_index(op.f("ix_queue_items_status"), table_name="queue_items")
    op.drop_table("queue_items")
