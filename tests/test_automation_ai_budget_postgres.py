"""Disposable PostgreSQL integration tests for automation AI budget safety."""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from alembic import command
from app.ai.usage import ProviderUsage
from app.core.config import Settings
from app.models.automation_ai_usage import AutomationAIUsageReservation
from app.models.automation_policy import AutomationPolicy
from app.models.automation_run import AutomationRun, AutomationRunItem
from app.models.product import Product
from app.models.workspace import Workspace
from app.services.automation_ai_budget import (
    AutomationAIBudgetExhausted,
    AutomationAIBudgetService,
    DuplicateAutomationAISubmission,
)

POSTGRES_URL = os.environ.get("TEST_POSTGRES_URL", "")
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not POSTGRES_URL, reason="Requires isolated TEST_POSTGRES_URL"),
]


def _settings(**overrides) -> Settings:
    values = {
        "_env_file": None,
        "automation_ai_budget_enabled": True,
        "automation_ai_workspace_daily_request_limit": 10,
        "automation_ai_global_daily_request_limit": 10,
        "automation_ai_workspace_daily_token_limit": 2_000_000,
        "automation_ai_global_daily_token_limit": 2_000_000,
        "automation_ai_max_output_tokens": 2048,
    }
    values.update(overrides)
    return Settings(**values)


@pytest.fixture(scope="module")
def postgres_migrated():
    if not POSTGRES_URL:
        pytest.skip("Requires isolated PostgreSQL")
    assert os.environ.get("DATABASE_URL") == POSTGRES_URL
    command.upgrade(Config("alembic.ini"), "022")
    yield


@pytest.fixture
async def pg_session_factory(postgres_migrated):
    engine = create_async_engine(POSTGRES_URL, pool_size=6, max_overflow=6)
    try:
        yield async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    finally:
        await engine.dispose()


async def test_migration_022_upgrade_downgrade_is_additive():
    config = Config("alembic.ini")
    await asyncio.to_thread(command.downgrade, config, "021")
    engine = create_async_engine(POSTGRES_URL)
    try:
        async with engine.connect() as connection:
            names = await connection.run_sync(lambda conn: set(inspect(conn).get_table_names()))
        assert "automation_ai_usage_reservations" not in names
    finally:
        await engine.dispose()

    await asyncio.to_thread(command.upgrade, config, "022")
    engine = create_async_engine(POSTGRES_URL)
    try:
        async with engine.connect() as connection:
            def inspect_budget_schema(conn):
                inspector = inspect(conn)
                table = "automation_ai_usage_reservations"
                return (
                    {col["name"] for col in inspector.get_columns(table)},
                    {item["name"] for item in inspector.get_unique_constraints(table)},
                    {item["name"] for item in inspector.get_check_constraints(table)},
                )

            details = await connection.run_sync(inspect_budget_schema)
        columns, unique, checks = details
        assert {"provider", "requested_model", "reserved_tokens", "status"} <= columns
        assert {"uq_automation_ai_usage_run_item", "uq_automation_ai_usage_submission"} <= unique
        assert "ck_automation_ai_usage_status" in checks
    finally:
        await engine.dispose()


async def _run_item(session_factory, label: str):
    now = datetime.now(UTC)
    async with session_factory() as session:
        workspace = Workspace(name=f"ai-budget-{label}-{uuid4().hex}")
        session.add(workspace)
        await session.flush()
        product = Product(
            title=f"AI budget test product {label}",
            price=Decimal("1.00"),
            image_url="https://example.test/product.jpg",
            product_url="https://example.test/product",
        )
        session.add(product)
        await session.flush()
        policy = AutomationPolicy(workspace_id=workspace.id)
        session.add(policy)
        await session.flush()
        run = AutomationRun(
            workspace_id=workspace.id,
            policy_id=policy.id,
            policy_revision=policy.revision,
            local_date=now.date(),
            scheduled_for=now,
            status="running",
            lease_owner="budget-test",
            lease_expires_at=now + timedelta(minutes=5),
        )
        session.add(run)
        await session.flush()
        item = AutomationRunItem(run_id=run.id, product_id=product.id, selection_rank=1)
        session.add(item)
        await session.commit()
        return workspace.id, run.id, item.id


async def _additional_item(session_factory, ids):
    async with session_factory() as session:
        product = Product(
            title=f"AI budget test product {uuid4().hex}",
            price=Decimal("1.00"),
            image_url="https://example.test/product.jpg",
            product_url="https://example.test/product",
        )
        session.add(product)
        await session.flush()
        item = AutomationRunItem(run_id=ids[1], product_id=product.id, selection_rank=2)
        session.add(item)
        await session.commit()
        return ids[0], ids[1], item.id


async def _reserve(session_factory, ids, *, timezone="UTC", settings=None, now=None):
    workspace_id, run_id, item_id = ids
    async with session_factory() as session:
        service = AutomationAIBudgetService(session, settings or _settings())
        return await service.reserve(
            workspace_id=workspace_id,
            run_id=run_id,
            run_item_id=item_id,
            timezone_name=timezone,
            plan=service.plan("openai", "gpt-4o-mini-2024-07-18"),
            now=now,
        )


async def test_concurrent_workspace_limit_admits_only_one_reservation(pg_session_factory):
    ids = await _run_item(pg_session_factory, "workspace-concurrent")
    second = await _additional_item(pg_session_factory, ids)
    now = datetime(2030, 1, 1, tzinfo=UTC)
    limits = _settings(automation_ai_workspace_daily_request_limit=1)
    async def attempt(item):
        try:
            await _reserve(pg_session_factory, item, settings=limits, now=now)
            return "admitted"
        except AutomationAIBudgetExhausted:
            return "blocked"
    results = await asyncio.gather(attempt(ids), attempt(second))
    assert sorted(results) == ["admitted", "blocked"]


async def test_concurrent_global_limit_serializes_different_workspaces(pg_session_factory):
    first = await _run_item(pg_session_factory, "global-a")
    second = await _run_item(pg_session_factory, "global-b")
    now = datetime(2030, 1, 2, tzinfo=UTC)
    limits = _settings(automation_ai_workspace_daily_request_limit=5,
                       automation_ai_global_daily_request_limit=1)
    results = await asyncio.gather(
        *(
            _reserve(pg_session_factory, item, settings=limits, now=now)
            for item in (first, second)
        ),
        return_exceptions=True,
    )
    assert sum(isinstance(result, UUID) for result in results) == 1
    assert sum(isinstance(result, AutomationAIBudgetExhausted) for result in results) == 1


async def test_reservation_settlement_and_uncertain_recovery_are_durable(pg_session_factory):
    ids = await _run_item(pg_session_factory, "settlement")
    reservation_id = await _reserve(pg_session_factory, ids)
    with pytest.raises(DuplicateAutomationAISubmission):
        await _reserve(pg_session_factory, ids)
    async with pg_session_factory() as session:
        service = AutomationAIBudgetService(session, _settings())
        assert await service.mark_submitted(reservation_id) is True
        usage = ProviderUsage(
            provider="openai",
            requested_model="gpt-4o-mini-2024-07-18",
            actual_model="gpt-4o-mini-2024-07-18",
            input_tokens=7,
            output_tokens=3,
            total_tokens=10,
            complete=True,
        )
        assert await service.settle(reservation_id, usage) == "settled"
        assert await service.settle(reservation_id, usage) == "settled"

    uncertain_ids = await _run_item(pg_session_factory, "uncertain")
    uncertain_id = await _reserve(pg_session_factory, uncertain_ids)
    async with pg_session_factory() as session:
        service = AutomationAIBudgetService(session, _settings())
        await service.mark_submitted(uncertain_id)
        await service.recover_interrupted_run(uncertain_ids[1])
        row = await session.scalar(
            select(AutomationAIUsageReservation).where(
                AutomationAIUsageReservation.provider_submission_id == uncertain_id
            )
        )
        assert row.status == "uncertain"
        assert row.reserved_tokens == 128_000 + 2048


async def test_incomplete_usage_keeps_conservative_token_reservation(pg_session_factory):
    ids = await _run_item(pg_session_factory, "incomplete-usage")
    reservation_id = await _reserve(
        pg_session_factory,
        ids,
        now=datetime(2030, 1, 5, tzinfo=UTC),
    )
    async with pg_session_factory() as session:
        service = AutomationAIBudgetService(session, _settings())
        await service.mark_submitted(reservation_id)
        incomplete = ProviderUsage(
            provider="openai",
            requested_model="gpt-4o-mini-2024-07-18",
            actual_model="gpt-4o-mini-2024-07-18",
            input_tokens=10,
            output_tokens=None,
            total_tokens=None,
            complete=False,
        )
        assert await service.settle(reservation_id, incomplete) == "uncertain"
        row = await session.scalar(
            select(AutomationAIUsageReservation).where(
                AutomationAIUsageReservation.provider_submission_id == reservation_id
            )
        )
        assert row.status == "uncertain"
        assert row.reserved_tokens == 128_000 + 2048
        assert row.usage_complete is False


async def test_workspace_timezone_bucket_and_daily_rollover(pg_session_factory):
    first = await _run_item(pg_session_factory, "dst-before")
    second = await _run_item(pg_session_factory, "dst-after")
    before = datetime(2026, 3, 8, 7, 59, tzinfo=UTC)
    after = datetime(2026, 3, 8, 8, 1, tzinfo=UTC)
    first_id = await _reserve(
        pg_session_factory, first, timezone="America/Los_Angeles", now=before
    )
    second_id = await _reserve(
        pg_session_factory, second, timezone="America/Los_Angeles", now=after
    )
    async with pg_session_factory() as session:
        first_row = await session.scalar(
            select(AutomationAIUsageReservation).where(
                AutomationAIUsageReservation.provider_submission_id == first_id
            )
        )
        second_row = await session.scalar(
            select(AutomationAIUsageReservation).where(
                AutomationAIUsageReservation.provider_submission_id == second_id
            )
        )
        assert first_row.workspace_usage_date == date(2026, 3, 7)
        assert second_row.workspace_usage_date == date(2026, 3, 8)
        assert first_row.global_usage_date == second_row.global_usage_date == date(2026, 3, 8)


async def test_token_reservation_exhaustion_prevents_a_second_submission(pg_session_factory):
    first = await _run_item(pg_session_factory, "tokens-a")
    second = await _run_item(pg_session_factory, "tokens-b")
    limits = _settings(
        automation_ai_workspace_daily_token_limit=130_048,
        automation_ai_global_daily_token_limit=130_048,
    )
    await _reserve(
        pg_session_factory,
        first,
        settings=limits,
        now=datetime(2030, 1, 4, tzinfo=UTC),
    )
    with pytest.raises(AutomationAIBudgetExhausted):
        await _reserve(
            pg_session_factory,
            second,
            settings=limits,
            now=datetime(2030, 1, 4, tzinfo=UTC),
        )
