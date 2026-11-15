"""Add Facebook destinations and provider-aware publish attempts.

Existing queue rows are Telegram rows. The migration is additive and does not
alter the historical migrations or reset existing data.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "019"
down_revision: str | None = "018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "queue_items",
        sa.Column("provider", sa.String(length=16), server_default="telegram", nullable=False),
    )
    op.add_column("queue_items", sa.Column("facebook_page_id", sa.UUID(), nullable=True))
    op.create_index(
        "ix_queue_items_provider", "queue_items", ["provider"], unique=False
    )
    op.create_index(
        "ix_queue_items_facebook_page_id",
        "queue_items",
        ["facebook_page_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_queue_items_facebook_page_id",
        "queue_items",
        "facebook_pages",
        ["facebook_page_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_queue_items_provider",
        "queue_items",
        "provider IN ('telegram', 'facebook')",
    )
    op.create_check_constraint(
        "ck_queue_items_destination_provider",
        "queue_items",
        "(provider = 'telegram' AND facebook_page_id IS NULL) OR "
        "(provider = 'facebook' AND channel_id IS NULL)",
    )

    op.add_column(
        "queue_publish_attempts",
        sa.Column("provider_message_ref", sa.String(length=255), nullable=True),
    )
    op.drop_constraint(
        "ck_queue_publish_attempts_provider_telegram",
        "queue_publish_attempts",
        type_="check",
    )
    op.drop_constraint(
        "ck_queue_publish_attempts_status",
        "queue_publish_attempts",
        type_="check",
    )
    op.drop_constraint(
        "ck_queue_publish_attempts_outcome_consistency",
        "queue_publish_attempts",
        type_="check",
    )
    op.create_check_constraint(
        "ck_queue_publish_attempts_provider",
        "queue_publish_attempts",
        "provider IN ('telegram', 'facebook')",
    )
    op.create_check_constraint(
        "ck_queue_publish_attempts_status",
        "queue_publish_attempts",
        "status IN ('started', 'succeeded', 'failed', 'ambiguous')",
    )
    op.create_check_constraint(
        "ck_queue_publish_attempts_outcome_consistency",
        "queue_publish_attempts",
        "("
        "status = 'started' AND error_code IS NULL AND error_message IS NULL "
        "AND provider_chat_id IS NULL AND provider_message_id IS NULL "
        "AND provider_message_ref IS NULL"
        ") OR ("
        "status = 'succeeded' AND error_code IS NULL AND error_message IS NULL "
        "AND ((provider = 'telegram' AND provider_chat_id IS NOT NULL "
        "AND provider_message_id IS NOT NULL) OR "
        "(provider = 'facebook' AND provider_message_ref IS NOT NULL))"
        ") OR ("
        "status IN ('failed', 'ambiguous') AND error_code IS NOT NULL "
        "AND error_message IS NOT NULL AND provider_chat_id IS NULL "
        "AND provider_message_id IS NULL AND provider_message_ref IS NULL"
        ")",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_queue_publish_attempts_outcome_consistency",
        "queue_publish_attempts",
        type_="check",
    )
    op.drop_constraint("ck_queue_publish_attempts_status", "queue_publish_attempts", type_="check")
    op.drop_constraint(
        "ck_queue_publish_attempts_provider",
        "queue_publish_attempts",
        type_="check",
    )
    op.create_check_constraint(
        "ck_queue_publish_attempts_provider_telegram",
        "queue_publish_attempts",
        "provider = 'telegram'",
    )
    op.create_check_constraint(
        "ck_queue_publish_attempts_status",
        "queue_publish_attempts",
        "status IN ('started', 'succeeded', 'failed')",
    )
    op.create_check_constraint(
        "ck_queue_publish_attempts_outcome_consistency",
        "queue_publish_attempts",
        "("
        "status = 'started' AND error_code IS NULL AND error_message IS NULL "
        "AND provider_chat_id IS NULL AND provider_message_id IS NULL"
        ") OR ("
        "status = 'succeeded' AND error_code IS NULL AND error_message IS NULL "
        "AND provider_chat_id IS NOT NULL AND provider_message_id IS NOT NULL"
        ") OR ("
        "status = 'failed' AND error_code IS NOT NULL AND error_message IS NOT NULL "
        "AND provider_chat_id IS NULL AND provider_message_id IS NULL"
        ")",
    )
    op.drop_column("queue_publish_attempts", "provider_message_ref")
    op.drop_constraint("ck_queue_items_destination_provider", "queue_items", type_="check")
    op.drop_constraint("ck_queue_items_provider", "queue_items", type_="check")
    op.drop_constraint("fk_queue_items_facebook_page_id", "queue_items", type_="foreignkey")
    op.drop_index("ix_queue_items_facebook_page_id", table_name="queue_items")
    op.drop_index("ix_queue_items_provider", table_name="queue_items")
    op.drop_column("queue_items", "facebook_page_id")
    op.drop_column("queue_items", "provider")
