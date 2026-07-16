"""Extend products table for AliExpress discovery metadata

Revision ID: 006
Revises: 005
Create Date: 2026-06-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("products", sa.Column("aliexpress_product_id", sa.String(length=64), nullable=True))
    op.add_column("products", sa.Column("description", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("original_price", sa.Numeric(precision=12, scale=2), nullable=True))
    op.add_column(
        "products",
        sa.Column("gallery_images", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("products", sa.Column("affiliate_url", sa.String(length=512), nullable=True))
    op.add_column("products", sa.Column("category", sa.String(length=255), nullable=True))
    op.add_column("products", sa.Column("store_name", sa.String(length=255), nullable=True))
    op.add_column(
        "products",
        sa.Column("currency", sa.String(length=8), server_default="USD", nullable=False),
    )
    op.add_column("products", sa.Column("commission_rate", sa.Numeric(precision=6, scale=2), nullable=True))
    op.add_column(
        "products",
        sa.Column("shipping_info", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("products", sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index(
        op.f("ix_products_aliexpress_product_id"),
        "products",
        ["aliexpress_product_id"],
        unique=True,
    )
    op.create_index(op.f("ix_products_category"), "products", ["category"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_products_category"), table_name="products")
    op.drop_index(op.f("ix_products_aliexpress_product_id"), table_name="products")
    op.drop_column("products", "last_synced_at")
    op.drop_column("products", "shipping_info")
    op.drop_column("products", "commission_rate")
    op.drop_column("products", "currency")
    op.drop_column("products", "store_name")
    op.drop_column("products", "category")
    op.drop_column("products", "affiliate_url")
    op.drop_column("products", "gallery_images")
    op.drop_column("products", "original_price")
    op.drop_column("products", "description")
    op.drop_column("products", "aliexpress_product_id")
