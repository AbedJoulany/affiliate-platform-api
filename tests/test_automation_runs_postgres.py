"""PostgreSQL migration and concurrency coverage for Phase 8C.3 run records."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from alembic import command
from app.models.automation_policy import AutomationPolicy
from app.models.automation_run import AutomationRun, AutomationRunItem
from app.models.workspace import Workspace
from app.repositories.automation_run import AutomationRunRepository

POSTGRES_URL = os.environ.get("TEST_POSTGRES_URL", "")
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not POSTGRES_URL, reason="Requires isolated TEST_POSTGRES_URL"),
]


@pytest.fixture(scope="module")
def postgres_migrated():
    if not POSTGRES_URL:
        pytest.skip("Requires isolated PostgreSQL")
    assert os.environ.get("DATABASE_URL") == POSTGRES_URL
    config = Config("alembic.ini")
    command.upgrade(config, "021")
    yield


@pytest.fixture
async def pg_session_factory(postgres_migrated):
    engine = create_async_engine(POSTGRES_URL, pool_size=5, max_overflow=5)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    finally:
        await engine.dispose()


async def _run_table_names() -> set[str]:
    engine = create_async_engine(POSTGRES_URL)
    try:
        async with engine.connect() as connection:
            return set(await connection.run_sync(lambda conn: inspect(conn).get_table_names()))
    finally:
        await engine.dispose()


async def _run_schema_details():
    engine = create_async_engine(POSTGRES_URL)
    try:
        async with engine.connect() as connection:
            def inspect_run_schema(conn):
                inspector = inspect(conn)
                return (
                    inspector.get_columns("automation_run_items"),
                    {item["name"] for item in inspector.get_unique_constraints("automation_runs")},
                    inspector.get_check_constraints("automation_run_items"),
                )

            return await connection.run_sync(inspect_run_schema)
    finally:
        await engine.dispose()


async def test_migration_021_upgrade_downgrade_and_schema_constraints():
    config = Config("alembic.ini")
    await asyncio.to_thread(command.downgrade, config, "020")
    run_tables = await _run_table_names()
    assert "automation_runs" not in run_tables
    assert "automation_run_items" not in run_tables

    await asyncio.to_thread(command.upgrade, config, "021")
    columns, unique_names, checks = await _run_schema_details()
    column_names = {column["name"] for column in columns}
    assert {"generated_content", "generation_state", "queue_item_id"} <= column_names
    assert "uq_automation_runs_workspace_policy_local_date" in unique_names
    assert {check["name"] for check in checks} >= {
        "ck_automation_run_items_status",
        "ck_automation_run_items_generation_state",
    }

    await asyncio.to_thread(command.downgrade, config, "020")
    run_tables = await _run_table_names()
    assert "automation_runs" not in run_tables
    assert "automation_run_items" not in run_tables
    # Keep the disposable CI database at the new head for the remaining tests.
    await asyncio.to_thread(command.upgrade, config, "021")


async def _workspace_policy(session_factory, label: str):
    async with session_factory() as session:
        workspace = Workspace(name=f"phase8c3-{label}-{uuid4().hex}")
        session.add(workspace)
        await session.flush()
        policy = AutomationPolicy(workspace_id=workspace.id)
        session.add(policy)
        await session.commit()
        await session.refresh(policy)
        return workspace.id, policy.id, policy.revision


async def _claim(session_factory, workspace_id, policy_id, revision, local_day, now):
    async with session_factory() as session:
        run = await AutomationRunRepository(session).claim_daily_run(
            workspace_id=workspace_id,
            policy_id=policy_id,
            policy_revision=revision,
            local_date=local_day,
            scheduled_for=now,
            lease_owner=f"pg-test:{uuid4()}",
            lease_expires_at=now + timedelta(minutes=10),
        )
        await session.commit()
        return run.id if run else None


async def test_concurrent_daily_claims_create_exactly_one_run(pg_session_factory):
    workspace_id, policy_id, revision = await _workspace_policy(pg_session_factory, "claim")
    now = datetime.now(UTC).replace(microsecond=0)
    results = await asyncio.gather(
        _claim(pg_session_factory, workspace_id, policy_id, revision, date(2026, 11, 23), now),
        _claim(pg_session_factory, workspace_id, policy_id, revision, date(2026, 11, 23), now),
    )
    assert sum(result is not None for result in results) == 1


async def test_concurrent_recovery_claims_have_exactly_one_lease_owner(pg_session_factory):
    workspace_id, policy_id, revision = await _workspace_policy(pg_session_factory, "recovery")
    now = datetime.now(UTC)
    async with pg_session_factory() as session:
        run = AutomationRun(
            workspace_id=workspace_id,
            policy_id=policy_id,
            policy_revision=revision,
            local_date=now.date(),
            scheduled_for=now - timedelta(minutes=1),
            status="claimed",
            lease_owner="",
            lease_expires_at=now - timedelta(seconds=1),
        )
        session.add(run)
        await session.commit()
        run_id = run.id

    async def _resume(owner: str) -> bool:
        async with pg_session_factory() as session:
            claimed = await AutomationRunRepository(session).resume_expired_claim(
                run_id,
                now=now,
                expected_lease_owner="",
                lease_owner=owner,
                lease_expires_at=now + timedelta(minutes=10),
            )
            await session.commit()
            return claimed

    owners = ["recovery-a", "recovery-b"]
    results = await asyncio.gather(*(_resume(owner) for owner in owners))
    assert sum(results) == 1

    async with pg_session_factory() as session:
        run = await AutomationRunRepository(session).get(run_id)
        assert run is not None
        assert run.lease_owner in owners
        assert run.lease_expires_at > datetime.now(UTC)


async def test_superseded_postgres_worker_cannot_lock_or_renew_run(pg_session_factory):
    workspace_id, policy_id, revision = await _workspace_policy(pg_session_factory, "fencing")
    now = datetime.now(UTC)
    async with pg_session_factory() as session:
        run = AutomationRun(
            workspace_id=workspace_id,
            policy_id=policy_id,
            policy_revision=revision,
            local_date=now.date(),
            scheduled_for=now,
            status="running",
            lease_owner="new-owner",
            lease_expires_at=now + timedelta(minutes=5),
        )
        session.add(run)
        await session.commit()
        run_id = run.id

    async with pg_session_factory() as session:
        repository = AutomationRunRepository(session)
        stale = await repository.lock_and_renew_owned_run(
            run_id,
            lease_owner="stale-owner",
            now=now,
            lease_duration=timedelta(minutes=10),
        )
        assert stale is None
        current = await repository.lock_and_renew_owned_run(
            run_id,
            lease_owner="new-owner",
            now=now,
            lease_duration=timedelta(minutes=10),
        )
        assert current is not None
        assert current.lease_owner == "new-owner"
        await session.commit()


async def test_concurrent_executor_starts_allow_only_one_owner_invocation(pg_session_factory):
    workspace_id, policy_id, revision = await _workspace_policy(pg_session_factory, "start")
    now = datetime.now(UTC)
    async with pg_session_factory() as session:
        run = AutomationRun(
            workspace_id=workspace_id,
            policy_id=policy_id,
            policy_revision=revision,
            local_date=now.date(),
            scheduled_for=now,
            status="claimed",
            lease_owner="same-owner",
            lease_expires_at=now + timedelta(minutes=5),
        )
        session.add(run)
        await session.commit()
        run_id = run.id

    async def _start():
        async with pg_session_factory() as session:
            started = await AutomationRunRepository(session).start_owned_run(
                run_id,
                lease_owner="same-owner",
                now=now,
                lease_duration=timedelta(minutes=10),
            )
            await session.commit()
            return started is not None

    results = await asyncio.gather(_start(), _start())
    assert sum(results) == 1

    async with pg_session_factory() as session:
        run = await AutomationRunRepository(session).get(run_id)
        assert run is not None
        assert run.status == "running"


async def test_run_items_persist_partial_results_and_uncertain_state(pg_session_factory):
    workspace_id, policy_id, revision = await _workspace_policy(pg_session_factory, "items")
    now = datetime.now(UTC).replace(microsecond=0)
    async with pg_session_factory() as session:
        run = AutomationRun(
            workspace_id=workspace_id,
            policy_id=policy_id,
            policy_revision=revision,
            local_date=date(2026, 11, 23),
            scheduled_for=now,
            status="running",
            lease_owner="test-worker",
            lease_expires_at=now + timedelta(minutes=10),
        )
        session.add(run)
        await session.flush()
        session.add_all(
            [
                AutomationRunItem(
                    run_id=run.id,
                    selection_rank=1,
                    status="generated",
                    generation_state="succeeded",
                    generated_content="reviewed content",
                    affiliate_url_snapshot="https://affiliate.example/item",
                ),
                AutomationRunItem(
                    run_id=run.id,
                    selection_rank=2,
                    status="uncertain",
                    generation_state="uncertain",
                    failure_category="provider_timeout",
                    failure_summary="Operator review required",
                ),
            ]
        )
        await session.commit()
        items = await AutomationRunRepository(session).items_for_run(run.id)
        assert [item.status for item in items] == ["generated", "uncertain"]
        assert items[0].generated_content == "reviewed content"
        assert items[1].generation_state == "uncertain"
