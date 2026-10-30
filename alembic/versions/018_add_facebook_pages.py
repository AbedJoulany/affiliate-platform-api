"""Add workspace-scoped Facebook Page connections.

The access token column stores only authenticated-encryption envelopes. The
encryption key remains application configuration and is never stored in the DB.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "018"
down_revision: str | None = "017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "facebook_pages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("facebook_page_id", sa.String(length=64), nullable=False),
        sa.Column("page_name", sa.String(length=255), nullable=False),
        sa.Column("encrypted_access_token", sa.Text(), nullable=False),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "validation_status",
            sa.String(length=16),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "workspace_id",
            "facebook_page_id",
            name="uq_facebook_pages_workspace_page_id",
        ),
    )
    op.create_index(
        "ix_facebook_pages_workspace_id", "facebook_pages", ["workspace_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_facebook_pages_workspace_id", table_name="facebook_pages")
    op.drop_table("facebook_pages")
