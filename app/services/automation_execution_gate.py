from __future__ import annotations

import logging
from typing import Any

from redis import asyncio as redis
from redis.exceptions import RedisError

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Positive latch: absent or unreadable means automation stays stopped. Deleting
# it stops work at the next check boundary; in-flight provider calls are not cancelled.
AUTOMATION_EXECUTION_LATCH_KEY = "product-a:automation:execution-enabled"
AUTOMATION_EXECUTION_LATCH_VALUE = "enabled"

_runtime_redis: Any | None = None


class AutomationExecutionStopped(RuntimeError):
    """Raised when the runtime stop check or saved policy blocks a run."""


class AutomationRunOwnershipLost(RuntimeError):
    """Raised when a worker no longer holds the active durable run lease."""


async def automation_execution_permitted(available: bool) -> bool:
    """Check the fail-closed runtime latch at each automation side-effect boundary."""
    if not available:
        return False

    global _runtime_redis
    try:
        if _runtime_redis is None:
            settings = get_settings()
            _runtime_redis = redis.from_url(
                settings.broker_url,
                socket_connect_timeout=1.0,
                socket_timeout=1.0,
                decode_responses=True,
            )
        return (
            await _runtime_redis.get(AUTOMATION_EXECUTION_LATCH_KEY)
            == AUTOMATION_EXECUTION_LATCH_VALUE
        )
    except (RedisError, TimeoutError, OSError, ConnectionError):
        logger.warning("Automation execution stop check failed; execution remains disabled")
        return False
