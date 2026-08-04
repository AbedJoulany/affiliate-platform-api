import asyncio
from collections.abc import Coroutine


def run_async[T](coro: Coroutine[object, object, T]) -> T:
    """Run an async coroutine from a sync Celery task.

    Disposes the shared async SQLAlchemy engine after each run so the next
    ``asyncio.run()`` does not reuse connections bound to a closed loop.
    """

    async def _runner() -> T:
        try:
            return await coro
        finally:
            from app.core.database import dispose_async_engine

            await dispose_async_engine()

    return asyncio.run(_runner())
