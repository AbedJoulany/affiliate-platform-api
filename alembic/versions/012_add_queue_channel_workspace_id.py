"""Add nullable workspace_id to queue_items and telegram_channels

Revision ID: 012
Revises: 011
Create Date: 2026-08-19

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "012"
down_revision: str | None = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "queue_items",
        sa.Column("workspace_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_queue_items_workspace_id_workspaces",
        "queue_items",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_queue_items_workspace_id",
        "queue_items",
        ["workspace_id"],
        unique=False,
    )

    op.add_column(
        "telegram_channels",
        sa.Column("workspace_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_telegram_channels_workspace_id_workspaces",
        "telegram_channels",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_telegram_channels_workspace_id",
        "telegram_channels",
        ["workspace_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_telegram_channels_workspace_id", table_name="telegram_channels")
    op.drop_constraint(
        "fk_telegram_channels_workspace_id_workspaces",
        "telegram_channels",
        type_="foreignkey",
    )
    op.drop_column("telegram_channels", "workspace_id")

    op.drop_index("ix_queue_items_workspace_id", table_name="queue_items")
    op.drop_constraint(
        "fk_queue_items_workspace_id_workspaces",
        "queue_items",
        type_="foreignkey",
    )
    op.drop_column("queue_items", "workspace_id")
