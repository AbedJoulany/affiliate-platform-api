"""Isolated PostgreSQL verification for Phase 5B policy persistence.

Run only against a disposable database with TEST_POSTGRES_URL set.
The normal SQLite test suite skips this module.
"""
from __future__ import annotations

import asyncio
import os
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.automation_policy import AutomationPolicy
from app.models.channel import TelegramChannel
from app.models.facebook_page import FacebookPage
from app.models.workspace import Workspace
from app.core.enums import BotPermissionStatus, FacebookPageValidationStatus, UserRole
from app.schemas.automation_policy import AutomationPolicyPatch
from app.services.automation_policy import AutomationPolicyService
from app.services.exceptions import ConflictError, ValidationError

POSTGRES_URL = os.environ.get("TEST_POSTGRES_URL", "")
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not POSTGRES_URL, reason="Requires isolated TEST_POSTGRES_URL"),
]


@pytest.fixture(scope="module")
def postgres_migrated():
    """Exercise real 019 -> 020 -> 019 -> 020 migration sequence."""
    if not POSTGRES_URL:
        pytest.skip("Requires isolated PostgreSQL")

    config = Config("alembic.ini")
    # Alembic's env.py reads DATABASE_URL from Settings.
    assert os.environ.get("DATABASE_URL") == POSTGRES_URL
    command.upgrade(config, "019")

    async def table_exists():
        engine = create_async_engine(POSTGRES_URL)
        try:
            async with engine.connect() as conn:
                return await conn.run_sync(
                    lambda sync: inspect(sync).has_table("automation_policies")
                )
        finally:
            await engine.dispose()

    assert not asyncio.run(table_exists()), "Revision 019 must not contain the table"
    command.upgrade(config, "020")
    assert asyncio.run(table_exists())
    command.downgrade(config, "019")
    assert not asyncio.run(table_exists())
    command.upgrade(config, "020")
    assert asyncio.run(table_exists())

    yield


@pytest.fixture
async def pg_db(postgres_migrated):
    engine = create_async_engine(POSTGRES_URL, pool_size=5, max_overflow=5)
    sessions = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    try:
        yield engine, sessions
    finally:
        await engine.dispose()


async def _workspace(sessions):
    async with sessions() as session:
        workspace = Workspace(name=f"PG policy test {uuid4().hex}")
        session.add(workspace)
        await session.commit()
        return workspace.id


class _Admin:
    role = UserRole.ADMIN


async def _attempt_patch(sessions, workspace_id, payload, gate):
    """Independent connection and transaction for every competing writer."""
    async with sessions() as session:
        await gate.wait()
        try:
            result = await AutomationPolicyService(session).patch(
                _Admin(), workspace_id, AutomationPolicyPatch.model_validate(payload)
            )
            await session.commit()
            return ("ok", result.revision)
        except ConflictError:
            await session.rollback()
            return ("conflict", None)


async def test_postgres_migration_constraints_and_indexes(pg_db):
    engine, sessions = pg_db

    async with engine.connect() as conn:
        def inspect_schema(sync):
            ins = inspect(sync)
            return (
                {col["name"] for col in ins.get_columns("automation_policies")},
                {row["name"] for row in ins.get_check_constraints("automation_policies")},
                ins.get_foreign_keys("automation_policies"),
                ins.get_unique_constraints("automation_policies"),
                {row["name"] for row in ins.get_indexes("automation_policies")},
            )
        columns, checks, foreign_keys, uniques, indexes = await conn.run_sync(inspect_schema)

    assert {
        "id", "workspace_id", "revision", "enabled",
        "telegram_channel_id", "facebook_page_id",
    } <= columns
    assert {
        "ck_automation_policies_provider",
        "ck_automation_policies_products_per_run",
    } <= checks
    assert any("workspace_id" in c["column_names"] for c in uniques)
    for column in ("telegram_channel_id", "facebook_page_id"):
        assert any(
            column in fk["constrained_columns"]
            and fk["options"].get("ondelete") == "SET NULL"
            for fk in foreign_keys
        )
        assert f"ix_automation_policies_{column}" in indexes

    workspace_id = await _workspace(sessions)
    async with sessions() as session:
        session.add(AutomationPolicy(workspace_id=workspace_id, products_per_run=0))
        with pytest.raises(Exception):
            await session.commit()
        await session.rollback()


async def test_postgres_concurrent_first_write_is_singleton(pg_db):
    _, sessions = pg_db
    workspace_id = await _workspace(sessions)
    gate = asyncio.Event()

    first = asyncio.create_task(
        _attempt_patch(
            sessions, workspace_id,
            {"expected_revision": 0, "discovery": {"products_per_run": 7}}, gate,
        )
    )
    second = asyncio.create_task(
        _attempt_patch(
            sessions, workspace_id,
            {"expected_revision": 0, "discovery": {"products_per_run": 9}}, gate,
        )
    )
    gate.set()
    results = await asyncio.wait_for(asyncio.gather(first, second), timeout=20)
    assert sorted(result[0] for result in results) == ["conflict", "ok"]
    async with sessions() as session:
        rows = (await session.execute(
            select(AutomationPolicy).where(AutomationPolicy.workspace_id == workspace_id)
        )).scalars().all()
        assert len(rows) == 1
        assert rows[0].revision == 1
        assert rows[0].products_per_run in {7, 9}


async def test_postgres_concurrent_stale_revision_is_rejected(pg_db):
    _, sessions = pg_db
    workspace_id = await _workspace(sessions)
    async with sessions() as session:
        await AutomationPolicyService(session).patch(
            _Admin(), workspace_id,
            AutomationPolicyPatch.model_validate({"expected_revision": 0}),
        )
        await session.commit()

    gate = asyncio.Event()
    first = asyncio.create_task(
        _attempt_patch(
            sessions, workspace_id,
            {"expected_revision": 1, "schedule": {"posts_per_day": 2}}, gate,
        )
    )
    second = asyncio.create_task(
        _attempt_patch(
            sessions, workspace_id,
            {"expected_revision": 1, "schedule": {"posts_per_day": 3}}, gate,
        )
    )
    gate.set()
    results = await asyncio.wait_for(asyncio.gather(first, second), timeout=20)
    assert sorted(result[0] for result in results) == ["conflict", "ok"]
    async with sessions() as session:
        row = (await session.execute(
            select(AutomationPolicy).where(AutomationPolicy.workspace_id == workspace_id)
        )).scalar_one()
        assert row.revision == 2
        assert row.posts_per_day in {2, 3}
        assert row.enabled is False


async def test_postgres_validation_rollback_keeps_revision_and_filters(pg_db):
    _, sessions = pg_db
    workspace_id = await _workspace(sessions)
    async with sessions() as session:
        await AutomationPolicyService(session).patch(
            _Admin(), workspace_id,
            AutomationPolicyPatch.model_validate(
                {"expected_revision": 0, "discovery": {"min_price": "2.00", "max_price": "10.00"}}
            ),
        )
        await session.commit()
    async with sessions() as session:
        with pytest.raises(ValidationError):
            await AutomationPolicyService(session).patch(
                _Admin(), workspace_id,
                AutomationPolicyPatch.model_validate(
                    {"expected_revision": 1, "discovery": {"min_price": "20.00"}}
                ),
            )
        await session.rollback()
    async with sessions() as session:
        row = (await session.execute(
            select(AutomationPolicy).where(AutomationPolicy.workspace_id == workspace_id)
        )).scalar_one()
        assert row.revision == 1
        assert str(row.min_price) == "2.00"
        assert str(row.max_price) == "10.00"


@pytest.mark.parametrize("kind", ["telegram", "facebook"])
async def test_postgres_destination_deletion_fails_closed(pg_db, kind):
    _, sessions = pg_db
    workspace_id = await _workspace(sessions)
    async with sessions() as session:
        if kind == "telegram":
            dest = TelegramChannel(
                workspace_id=workspace_id,
                telegram_channel_id=f"pg-{uuid4().hex}",
                title="PG test channel",
                bot_permission_status=BotPermissionStatus.GRANTED,
                can_post_messages=True,
                can_edit_messages=True,
                can_delete_messages=True,
                is_active=True,
            )
        else:
            dest = FacebookPage(
                workspace_id=workspace_id,
                facebook_page_id=f"pg-{uuid4().hex}",
                page_name="PG test page",
                encrypted_access_token="isolated-test-placeholder",
                validation_status=FacebookPageValidationStatus.VALID,
                is_active=True,
            )
        session.add(dest)
        await session.commit()
        dest_id = dest.id

    destination = (
        {"provider": "telegram", "channel_id": str(dest_id)}
        if kind == "telegram" else {"provider": "facebook", "page_id": str(dest_id)}
    )
    async with sessions() as session:
        result = await AutomationPolicyService(session).patch(
            _Admin(), workspace_id,
            AutomationPolicyPatch.model_validate({
                "expected_revision": 0, "enabled": True, "destination": destination
            }),
        )
        assert result.enabled is True
        assert result.configuration_ready is True
        assert result.execution_available is False
        await session.commit()

    async with sessions() as session:
        target = await session.get(TelegramChannel if kind == "telegram" else FacebookPage, dest_id)
        await session.delete(target)
        await session.commit()

    async with sessions() as session:
        row = (await session.execute(
            select(AutomationPolicy).where(AutomationPolicy.workspace_id == workspace_id)
        )).scalar_one()
        assert row.telegram_channel_id is None
        assert row.facebook_page_id is None
        result = await AutomationPolicyService(session).get(_Admin(), workspace_id)
        assert result.destination is None
        assert result.configuration_ready is False
        assert result.execution_available is False
