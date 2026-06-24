"""Add publishing fields to queue_items

Revision ID: 005
Revises: 004
Create Date: 2026-06-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("queue_items", sa.Column("image_url", sa.String(length=512), nullable=True))
    op.add_column("queue_items", sa.Column("button_text", sa.String(length=128), nullable=True))
    op.add_column("queue_items", sa.Column("button_url", sa.String(length=512), nullable=True))
    op.add_column("queue_items", sa.Column("telegram_message_id", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("queue_items", "telegram_message_id")
    op.drop_column("queue_items", "button_url")
    op.drop_column("queue_items", "button_text")
    op.drop_column("queue_items", "image_url")
