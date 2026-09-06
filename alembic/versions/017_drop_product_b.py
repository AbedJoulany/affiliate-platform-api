"""Drop Product B affiliate-network tables and normalize user roles.

Revision ID: 017
Revises: 016
Create Date: 2026-09-06

Does not rewrite 001–016. Drops clicks, conversions, affiliate_campaigns,
affiliates, and campaigns in foreign-key order. Maps leftover
``affiliate`` / ``advertiser`` user roles to ``user``.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "017"
down_revision: str | None = "016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(
        "ix_conversions_campaign_id_created_at_status",
        table_name="conversions",
    )
    op.drop_index(
        "ix_clicks_affiliate_campaign_id_created_at",
        table_name="clicks",
    )
    op.drop_index(op.f("ix_clicks_click_id"), table_name="clicks")
    op.drop_index(op.f("ix_clicks_affiliate_campaign_id"), table_name="clicks")
    op.drop_table("clicks")

    op.drop_index(op.f("ix_conversions_click_id"), table_name="conversions")
    op.drop_index(op.f("ix_conversions_campaign_id"), table_name="conversions")
    op.drop_index(op.f("ix_conversions_affiliate_id"), table_name="conversions")
    op.drop_table("conversions")

    op.drop_index(op.f("ix_affiliate_campaigns_campaign_id"), table_name="affiliate_campaigns")
    op.drop_index(op.f("ix_affiliate_campaigns_affiliate_id"), table_name="affiliate_campaigns")
    op.drop_table("affiliate_campaigns")

    op.drop_index(op.f("ix_affiliates_referral_code"), table_name="affiliates")
    op.drop_table("affiliates")

    op.drop_index("ix_campaigns_workspace_id", table_name="campaigns")
    op.drop_index(op.f("ix_campaigns_name"), table_name="campaigns")
    op.drop_index(op.f("ix_campaigns_advertiser_id"), table_name="campaigns")
    op.drop_table("campaigns")

    op.execute(
        sa.text("UPDATE users SET role = 'user' WHERE role IN ('affiliate', 'advertiser')")
    )


def downgrade() -> None:
    op.execute(
        sa.text("UPDATE users SET role = 'affiliate' WHERE role = 'user'")
    )

    op.create_table(
        "campaigns",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("advertiser_id", sa.UUID(), nullable=True),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "draft", "active", "paused", "completed", name="campaign_status", native_enum=False
            ),
            nullable=False,
        ),
        sa.Column("payout_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("landing_url", sa.String(length=512), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["advertiser_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            name="fk_campaigns_workspace_id_workspaces",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_campaigns_advertiser_id"), "campaigns", ["advertiser_id"], unique=False
    )
    op.create_index(op.f("ix_campaigns_name"), "campaigns", ["name"], unique=False)
    op.create_index("ix_campaigns_workspace_id", "campaigns", ["workspace_id"], unique=False)

    op.create_table(
        "affiliates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("website", sa.String(length=512), nullable=True),
        sa.Column("referral_code", sa.String(length=32), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "active",
                "suspended",
                "rejected",
                name="affiliate_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("commission_rate", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("payout_details", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index(
        op.f("ix_affiliates_referral_code"), "affiliates", ["referral_code"], unique=True
    )

    op.create_table(
        "affiliate_campaigns",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("affiliate_id", sa.UUID(), nullable=False),
        sa.Column("campaign_id", sa.UUID(), nullable=False),
        sa.Column("tracking_link", sa.String(length=512), nullable=False),
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
        sa.ForeignKeyConstraint(["affiliate_id"], ["affiliates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("affiliate_id", "campaign_id", name="uq_affiliate_campaign"),
    )
    op.create_index(
        op.f("ix_affiliate_campaigns_affiliate_id"),
        "affiliate_campaigns",
        ["affiliate_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_affiliate_campaigns_campaign_id"),
        "affiliate_campaigns",
        ["campaign_id"],
        unique=False,
    )

    op.create_table(
        "conversions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("affiliate_id", sa.UUID(), nullable=False),
        sa.Column("campaign_id", sa.UUID(), nullable=False),
        sa.Column("external_order_id", sa.String(length=128), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("commission", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "approved",
                "rejected",
                "paid",
                name="conversion_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("click_id", sa.String(length=64), nullable=True),
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
        sa.ForeignKeyConstraint(["affiliate_id"], ["affiliates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_order_id"),
    )
    op.create_index(
        op.f("ix_conversions_affiliate_id"), "conversions", ["affiliate_id"], unique=False
    )
    op.create_index(
        op.f("ix_conversions_campaign_id"), "conversions", ["campaign_id"], unique=False
    )
    op.create_index(op.f("ix_conversions_click_id"), "conversions", ["click_id"], unique=False)
    op.create_index(
        "ix_conversions_campaign_id_created_at_status",
        "conversions",
        ["campaign_id", "created_at", "status"],
        unique=False,
    )

    op.create_table(
        "clicks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("affiliate_campaign_id", sa.UUID(), nullable=False),
        sa.Column("click_id", sa.String(length=64), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["affiliate_campaign_id"],
            ["affiliate_campaigns.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_clicks_affiliate_campaign_id"),
        "clicks",
        ["affiliate_campaign_id"],
        unique=False,
    )
    op.create_index(op.f("ix_clicks_click_id"), "clicks", ["click_id"], unique=True)
    op.create_index(
        "ix_clicks_affiliate_campaign_id_created_at",
        "clicks",
        ["affiliate_campaign_id", "created_at"],
        unique=False,
    )
