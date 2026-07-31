"""Add queue_publish_attempts table

Revision ID: 008
Revises: 007
Create Date: 2026-07-29

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "queue_publish_attempts",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("queue_id", sa.UUID(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column(
            "provider",
            sa.String(length=32),
            server_default="telegram",
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="started",
            nullable=False,
        ),
        sa.Column("content_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("idempotency_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("provider_chat_id", sa.String(length=64), nullable=True),
        sa.Column("provider_message_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
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
        sa.CheckConstraint(
            "attempt_number > 0",
            name="ck_queue_publish_attempts_attempt_number_positive",
        ),
        sa.CheckConstraint(
            "provider = 'telegram'",
            name="ck_queue_publish_attempts_provider_telegram",
        ),
        sa.CheckConstraint(
            "status IN ('started', 'succeeded', 'failed')",
            name="ck_queue_publish_attempts_status",
        ),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'",
            name="ck_queue_publish_attempts_content_hash_format",
        ),
        sa.CheckConstraint(
            "("
            "status = 'started' "
            "AND error_code IS NULL "
            "AND error_message IS NULL "
            "AND provider_chat_id IS NULL "
            "AND provider_message_id IS NULL"
            ") OR ("
            "status = 'succeeded' "
            "AND error_code IS NULL "
            "AND error_message IS NULL "
            "AND provider_chat_id IS NOT NULL "
            "AND provider_message_id IS NOT NULL"
            ") OR ("
            "status = 'failed' "
            "AND error_code IS NOT NULL "
            "AND error_message IS NOT NULL "
            "AND provider_chat_id IS NULL "
            "AND provider_message_id IS NULL"
            ")",
            name="ck_queue_publish_attempts_outcome_consistency",
        ),
        sa.ForeignKeyConstraint(
            ["queue_id"],
            ["queue_items.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "queue_id",
            "attempt_number",
            name="uq_queue_publish_attempts_queue_id_attempt_number",
        ),
    )
    op.create_index(
        "ix_queue_publish_attempts_guard_lookup",
        "queue_publish_attempts",
        ["queue_id", "content_hash", "status", "idempotency_expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_queue_publish_attempts_provider_status_occurred",
        "queue_publish_attempts",
        ["provider", "status", "occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_queue_publish_attempts_provider_status_occurred",
        table_name="queue_publish_attempts",
    )
    op.drop_index(
        "ix_queue_publish_attempts_guard_lookup",
        table_name="queue_publish_attempts",
    )
    op.drop_table("queue_publish_attempts")
