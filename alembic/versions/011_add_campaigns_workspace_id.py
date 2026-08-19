"""Add nullable campaigns.workspace_id

Revision ID: 011
Revises: 010
Create Date: 2026-08-17

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "campaigns",
        sa.Column("workspace_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_campaigns_workspace_id_workspaces",
        "campaigns",
        "workspaces",
        ["workspace_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_campaigns_workspace_id",
        "campaigns",
        ["workspace_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_campaigns_workspace_id", table_name="campaigns")
    op.drop_constraint(
        "fk_campaigns_workspace_id_workspaces",
        "campaigns",
        type_="foreignkey",
    )
    op.drop_column("campaigns", "workspace_id")
