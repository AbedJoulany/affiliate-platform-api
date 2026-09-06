"""Operator backfill for leftover NULL workspace_id rows (pre-alembic 013)."""

from uuid import uuid4

import pytest

from app.models.workspace import Workspace
from scripts.assign_legacy_workspace_ids import (
    assign_legacy_workspace_ids,
    count_null_workspace_rows,
)


@pytest.mark.asyncio
async def test_assign_legacy_workspace_ids_rejects_missing_workspace(session):
    with pytest.raises(ValueError, match="does not exist"):
        await assign_legacy_workspace_ids(session, uuid4())


@pytest.mark.asyncio
async def test_assign_legacy_workspace_ids_noop_when_no_nulls(session):
    workspace = Workspace(name="Only workspace")
    session.add(workspace)
    await session.flush()

    remaining = await assign_legacy_workspace_ids(session, workspace.id)
    counts = await count_null_workspace_rows(session)
    assert remaining.total == 0
    assert counts.total == 0
