"""Close Stage-1 workspace_id: fail-closed NOT NULL and ON DELETE RESTRICT

Revision ID: 013
Revises: 012
Create Date: 2026-08-19

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision: str = "013"
down_revision: str | None = "012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_WORKSPACE_TABLES = ("campaigns", "queue_items", "telegram_channels")

_FK_SPECS = (
    ("fk_campaigns_workspace_id_workspaces", "campaigns"),
    ("fk_queue_items_workspace_id_workspaces", "queue_items"),
    ("fk_telegram_channels_workspace_id_workspaces", "telegram_channels"),
)


def null_workspace_counts(connection) -> dict[str, int]:
    """Count tenant rows that still lack a workspace_id."""
    counts: dict[str, int] = {}
    for table in TENANT_WORKSPACE_TABLES:
        result = connection.execute(
            text(f"SELECT COUNT(*) FROM {table} WHERE workspace_id IS NULL")
        )
        counts[table] = int(result.scalar() or 0)
    return counts


def raise_if_null_workspace_rows(counts: dict[str, int]) -> None:
    """Abort schema closeout when any tenant row is still unassigned."""
    unresolved = {table: count for table, count in counts.items() if count > 0}
    if not unresolved:
        return
    details = ", ".join(f"{table}={count}" for table, count in unresolved.items())
    raise RuntimeError(
        "Cannot set workspace_id NOT NULL while NULL rows exist: "
        f"{details}. Assign or remove those rows explicitly, then retry. "
        "No automatic backfill is performed."
    )


def upgrade() -> None:
    bind = op.get_bind()
    raise_if_null_workspace_rows(null_workspace_counts(bind))

    for fk_name, table in _FK_SPECS:
        op.drop_constraint(fk_name, table, type_="foreignkey")
        op.create_foreign_key(
            fk_name,
            table,
            "workspaces",
            ["workspace_id"],
            ["id"],
            ondelete="RESTRICT",
        )

    for table in TENANT_WORKSPACE_TABLES:
        op.alter_column(
            table,
            "workspace_id",
            existing_type=sa.UUID(),
            nullable=False,
        )


def downgrade() -> None:
    for table in TENANT_WORKSPACE_TABLES:
        op.alter_column(
            table,
            "workspace_id",
            existing_type=sa.UUID(),
            nullable=True,
        )

    for fk_name, table in _FK_SPECS:
        op.drop_constraint(fk_name, table, type_="foreignkey")
        op.create_foreign_key(
            fk_name,
            table,
            "workspaces",
            ["workspace_id"],
            ["id"],
            ondelete="SET NULL",
        )
