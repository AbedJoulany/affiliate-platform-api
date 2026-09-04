"""Add aliexpress_categories cache table

Revision ID: 007
Revises: 006
Create Date: 2026-06-05

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "aliexpress_categories",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("category_name", sa.String(length=255), nullable=False),
        sa.Column("parent_category_id", sa.Integer(), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
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
        op.f("ix_aliexpress_categories_category_id"),
        "aliexpress_categories",
        ["category_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_aliexpress_categories_category_id"), table_name="aliexpress_categories")
    op.drop_table("aliexpress_categories")
