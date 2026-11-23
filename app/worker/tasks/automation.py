"""Phase 8C periodic automation dispatcher, intentionally disabled by default."""

from app.core.config import get_settings
from app.core.database import get_async_session_maker
from app.services.automation_orchestration import (
    AutomationOrchestrationService,
    automation_execution_available,
)
from app.worker.async_utils import run_async
from app.worker.celery_app import celery_app


async def _dispatch_due_automations() -> dict:
    session_maker = get_async_session_maker()
    async with session_maker() as session:
        return await AutomationOrchestrationService(session).dispatch_due()


@celery_app.task(name="app.worker.tasks.automation.dispatch_due_automations")
def dispatch_due_automations() -> dict[str, int | str]:
    """Periodic entry point; returns before DB access while activation is unavailable."""
    if not automation_execution_available(get_settings()):
        return {"status": "disabled", "claimed": 0, "missed": 0}
    return run_async(_dispatch_due_automations())
