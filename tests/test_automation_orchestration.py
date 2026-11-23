from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.enums import ProductStatus
from app.models.automation_policy import AutomationPolicy
from app.models.automation_run import AutomationRun, AutomationRunItem
from app.models.product import Product
from app.models.workspace import Workspace
from app.repositories.automation_run import AutomationRunRepository
from app.services.automation_orchestration import (
    AutomationOrchestrationService,
    automation_execution_available,
    daily_slot,
)
from app.worker.tasks.automation import dispatch_due_automations

pytestmark = pytest.mark.asyncio


async def _workspace_policy(session) -> tuple[Workspace, AutomationPolicy]:
    workspace = Workspace(name=f"orchestration-{uuid4()}")
    session.add(workspace)
    await session.flush()
    policy = AutomationPolicy(workspace_id=workspace.id)
    session.add(policy)
    await session.flush()
    return workspace, policy


async def test_execution_gate_remains_closed_even_if_global_flag_is_set():
    settings = Settings(
        automation_execution_enabled=True,
        automation_emergency_stop=False,
    )
    assert automation_execution_available(settings) is False


async def test_dispatcher_returns_without_database_or_provider_work(monkeypatch):
    settings = Settings(
        automation_execution_enabled=True,
        automation_emergency_stop=False,
    )

    def fail_if_database_is_opened():
        raise AssertionError("disabled dispatcher must not open a database session")

    monkeypatch.setattr("app.worker.tasks.automation.get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.worker.tasks.automation.get_async_session_maker",
        fail_if_database_is_opened,
    )
    assert dispatch_due_automations.run() == {
        "status": "disabled",
        "claimed": 0,
        "missed": 0,
    }


async def test_daily_slot_uses_workspace_local_date_and_dst_resolution():
    spring_day = datetime(2026, 3, 8, 12, tzinfo=UTC)
    local_date, spring_slot = daily_slot(spring_day, "America/New_York", time(2, 30))
    assert local_date == date(2026, 3, 8)
    # 02:30 does not exist; the shared scheduler moves to the first valid minute.
    assert spring_slot == datetime(2026, 3, 8, 7, tzinfo=UTC)

    fall_day = datetime(2026, 11, 1, 12, tzinfo=UTC)
    local_date, fall_slot = daily_slot(fall_day, "America/New_York", time(1, 30))
    assert local_date == date(2026, 11, 1)
    # Ambiguous fall-back time resolves to the earlier occurrence (fold=0).
    assert fall_slot == datetime(2026, 11, 1, 5, 30, tzinfo=UTC)


async def test_daily_run_identity_excludes_policy_revision_and_is_workspace_scoped(session):
    workspace, policy = await _workspace_policy(session)
    now = datetime.now(UTC).replace(microsecond=0)
    repo = AutomationRunRepository(session)
    first = await repo.claim_daily_run(
        workspace_id=workspace.id,
        policy_id=policy.id,
        policy_revision=policy.revision,
        local_date=date(2026, 11, 23),
        scheduled_for=now,
        lease_owner="test-worker-a",
        lease_expires_at=now + timedelta(minutes=10),
    )
    assert first is not None
    await session.commit()

    # A changed policy revision cannot produce another logical daily run.
    duplicate = await repo.claim_daily_run(
        workspace_id=workspace.id,
        policy_id=policy.id,
        policy_revision=policy.revision + 1,
        local_date=date(2026, 11, 23),
        scheduled_for=now,
        lease_owner="test-worker-b",
        lease_expires_at=now + timedelta(minutes=10),
    )
    assert duplicate is None

    other_workspace, other_policy = await _workspace_policy(session)
    other = await repo.claim_daily_run(
        workspace_id=other_workspace.id,
        policy_id=other_policy.id,
        policy_revision=other_policy.revision,
        local_date=date(2026, 11, 23),
        scheduled_for=now,
        lease_owner="test-worker-c",
        lease_expires_at=now + timedelta(minutes=10),
    )
    assert other is not None


async def test_expired_started_generation_is_marked_uncertain_and_never_resumed(session):
    workspace, policy = await _workspace_policy(session)
    now = datetime.now(UTC).replace(microsecond=0)
    run = AutomationRun(
        workspace_id=workspace.id,
        policy_id=policy.id,
        policy_revision=policy.revision,
        local_date=date(2026, 11, 23),
        scheduled_for=now,
        status="running",
        lease_owner="lost-worker",
        lease_expires_at=now - timedelta(seconds=1),
    )
    session.add(run)
    await session.flush()
    item = AutomationRunItem(
        run_id=run.id,
        product_id=None,
        selection_rank=1,
        status="generating",
        generation_state="started",
        generation_started_at=now - timedelta(minutes=2),
    )
    session.add(item)
    await session.commit()

    resumable = await AutomationOrchestrationService(session)._recover_expired(now)
    assert resumable == []
    assert run.status == "needs_operator_review"
    assert item.generation_state == "uncertain"
    assert item.status == "uncertain"


async def test_orchestration_exception_after_generation_start_requires_review(session, monkeypatch):
    # Exercise the protected post-generation failure path in isolation. The
    # production execution gates remain hardcoded closed in Phase 8C.3.
    monkeypatch.setattr(
        "app.services.automation_orchestration.automation_execution_available",
        lambda *_args, **_kwargs: True,
    )
    workspace, policy = await _workspace_policy(session)
    policy.enabled = True
    now = datetime.now(UTC).replace(microsecond=0)
    run = AutomationRun(
        workspace_id=workspace.id,
        policy_id=policy.id,
        policy_revision=policy.revision,
        local_date=date(2026, 11, 23),
        scheduled_for=now,
        status="claimed",
        lease_owner="test-worker",
        lease_expires_at=now + timedelta(minutes=10),
    )
    session.add(run)
    await session.flush()
    item = AutomationRunItem(
        run_id=run.id,
        product_id=None,
        selection_rank=1,
        status="selected",
        generation_state="not_started",
    )
    session.add(item)
    await session.commit()

    service = AutomationOrchestrationService(session)

    async def fake_preflight(*_args, **_kwargs):
        return policy, None, "UTC"

    async def fail_after_provider_may_have_started(_run, *_args):
        item.status = "generating"
        item.generation_state = "started"
        item.generation_started_at = datetime.now(UTC)
        await session.commit()
        raise RuntimeError("simulated worker-side failure")

    monkeypatch.setattr(service.queue, "_preflight", fake_preflight)
    monkeypatch.setattr(service, "_execute_pipeline", fail_after_provider_may_have_started)

    result = await service.execute_claimed_run(run.id)

    assert result["status"] == "needs_operator_review"
    assert run.status == "needs_operator_review"
    assert item.generation_state == "uncertain"
    assert item.status == "uncertain"


async def test_expired_run_before_generation_can_be_claimed_again(session):
    workspace, policy = await _workspace_policy(session)
    now = datetime.now(UTC).replace(microsecond=0)
    run = AutomationRun(
        workspace_id=workspace.id,
        policy_id=policy.id,
        policy_revision=policy.revision,
        local_date=date(2026, 11, 23),
        scheduled_for=now - timedelta(minutes=1),
        status="running",
        lease_owner="lost-worker",
        lease_expires_at=now - timedelta(seconds=1),
    )
    session.add(run)
    await session.commit()

    resumable = await AutomationOrchestrationService(session)._recover_expired(now)
    assert resumable == [run.id]
    claimed = await AutomationRunRepository(session).resume_expired_claim(
        run.id,
        now=now,
        lease_owner="recovery-worker",
        lease_expires_at=now + timedelta(minutes=10),
    )
    assert claimed is True
    await session.commit()
    assert run.lease_owner == "recovery-worker"


async def test_expired_run_outside_recovery_window_is_missed(session):
    workspace, policy = await _workspace_policy(session)
    now = datetime.now(UTC).replace(microsecond=0)
    run = AutomationRun(
        workspace_id=workspace.id,
        policy_id=policy.id,
        policy_revision=policy.revision,
        local_date=date(2026, 11, 22),
        scheduled_for=now - timedelta(days=1),
        status="running",
        lease_owner="lost-worker",
        lease_expires_at=now - timedelta(minutes=6),
    )
    session.add(run)
    await session.commit()

    resumable = await AutomationOrchestrationService(session)._recover_expired(now)

    assert resumable == []
    assert run.status == "missed"
    assert run.error_category == "recovery_window_expired"


async def test_partial_generation_recovery_does_not_repeat_ai_batch(session, monkeypatch):
    workspace, policy = await _workspace_policy(session)
    completed_product = Product(
        aliexpress_product_id=f"phase8c3-{uuid4().hex}",
        title="Persisted generated product",
        price=Decimal("10.00"),
        image_url="https://example.com/image.jpg",
        product_url="https://example.com/product",
        affiliate_url="https://affiliate.example/item",
        status=ProductStatus.ACTIVE,
    )
    pending_product = Product(
        aliexpress_product_id=f"phase8c3-{uuid4().hex}",
        title="Not yet generated product",
        price=Decimal("12.00"),
        image_url="https://example.com/image.jpg",
        product_url="https://example.com/product",
        affiliate_url="https://affiliate.example/item-2",
        status=ProductStatus.ACTIVE,
    )
    session.add_all([completed_product, pending_product])
    await session.flush()
    now = datetime.now(UTC).replace(microsecond=0)
    run = AutomationRun(
        workspace_id=workspace.id,
        policy_id=policy.id,
        policy_revision=policy.revision,
        local_date=date(2026, 11, 23),
        scheduled_for=now,
        status="running",
    )
    session.add(run)
    await session.flush()
    completed = AutomationRunItem(
        run_id=run.id,
        product_id=completed_product.id,
        selection_rank=1,
        status="generated",
        generation_state="succeeded",
        generated_content="persisted content",
        affiliate_url_snapshot="https://affiliate.example/item",
    )
    pending = AutomationRunItem(
        run_id=run.id,
        product_id=pending_product.id,
        selection_rank=2,
        status="selected",
        generation_state="not_started",
    )
    session.add_all([completed, pending])
    await session.commit()

    async def fail_if_regenerated(*_args, **_kwargs):
        raise AssertionError("recovery must not repeat the AI generation batch")

    monkeypatch.setattr(
        "app.services.automation_orchestration.AutomationContentGenerationService.preview_for_run",
        fail_if_regenerated,
    )
    service = AutomationOrchestrationService(session)

    async def fake_preflight(*_args, **_kwargs):
        return policy, None, "UTC"

    async def fake_create_one(*_args, **_kwargs):
        return SimpleNamespace(status="scheduled", error_category=None)

    monkeypatch.setattr(service.queue, "_preflight", fake_preflight)
    monkeypatch.setattr(service.queue, "_create_one", fake_create_one)
    await service._execute_pipeline(run, policy, None, "UTC")

    assert completed.generated_content == "persisted content"
    assert completed.status == "generated"
    assert completed.queue_item_id is None
    assert pending.status == "skipped"
    assert pending.failure_category == "recovery_generation_not_repeated"
    assert run.status == "completed_with_errors"
