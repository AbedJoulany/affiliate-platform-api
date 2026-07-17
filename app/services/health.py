import asyncio

from redis import asyncio as redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.schemas.health import DependencyStatus, ReadinessResponse


class ReadinessService:
    CHECK_TIMEOUT_SECONDS = 2.0

    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.settings = settings or get_settings()

    async def check(self) -> ReadinessResponse:
        database_up, redis_up = await asyncio.gather(
            self._check_database(),
            self._check_redis(),
        )
        ready = database_up and redis_up
        return ReadinessResponse(
            status="ready" if ready else "not_ready",
            checks={
                "database": DependencyStatus(status="up" if database_up else "down"),
                "redis": DependencyStatus(status="up" if redis_up else "down"),
            },
        )

    async def _check_database(self) -> bool:
        try:
            async with asyncio.timeout(self.CHECK_TIMEOUT_SECONDS):
                await self.session.execute(text("SELECT 1"))
        except Exception:
            try:
                async with asyncio.timeout(self.CHECK_TIMEOUT_SECONDS):
                    await self.session.rollback()
            except Exception:
                pass
            return False
        return True

    async def _check_redis(self) -> bool:
        client = None
        try:
            client = redis.from_url(
                self.settings.broker_url,
                socket_connect_timeout=self.CHECK_TIMEOUT_SECONDS,
                socket_timeout=self.CHECK_TIMEOUT_SECONDS,
            )
            async with asyncio.timeout(self.CHECK_TIMEOUT_SECONDS):
                return bool(await client.ping())
        except Exception:
            return False
        finally:
            if client is not None:
                try:
                    async with asyncio.timeout(self.CHECK_TIMEOUT_SECONDS):
                        await client.aclose()
                except Exception:
                    pass
