from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis import asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.database import get_db
from app.events.consumer import EventConsumer
from app.events.deps import get_event_broadcaster
from app.schemas.health import ReadinessResponse, WorkerHealthResponse
from app.services.exceptions import ServiceError
from app.services.health import ReadinessService
from app.services.worker_health import WorkerHealthService

settings = get_settings()


class SecurityHeadersMiddleware:
    """Attach security headers without buffering response bodies.

    ``@app.middleware("http")`` / ``BaseHTTPMiddleware`` consumes streaming
    responses into memory and breaks SSE. This pure ASGI wrapper only mutates
    ``http.response.start`` headers.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                headers["Permissions-Policy"] = (
                    "camera=(), microphone=(), geolocation=()"
                )
            await send(message)

        await self.app(scope, receive, send_with_headers)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start/stop the Redis Pub/Sub event consumer for SSE fan-out."""
    broadcaster = get_event_broadcaster()
    redis_client = redis.from_url(settings.broker_url)
    consumer = EventConsumer(redis_client, broadcaster)
    app.state.event_consumer = consumer
    app.state.event_redis = redis_client
    await consumer.start()
    try:
        yield
    finally:
        await consumer.stop()
        app.state.event_consumer = None
        try:
            await redis_client.aclose()
        finally:
            app.state.event_redis = None


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)


@app.exception_handler(ServiceError)
async def service_error_handler(_: Request, exc: ServiceError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", response_model=ReadinessResponse, tags=["Health"])
async def readiness_check(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ReadinessResponse:
    readiness = await ReadinessService(db).check()
    if readiness.status == "not_ready":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return readiness


@app.get("/worker/health", response_model=WorkerHealthResponse, tags=["Health"])
async def worker_health_check(response: Response) -> WorkerHealthResponse:
    """Celery Beat/worker pipeline liveness from the Task 1 Redis heartbeat."""
    result = await WorkerHealthService().check()
    if result.status != "healthy":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return result


app.include_router(api_router, prefix=settings.api_v1_prefix)
