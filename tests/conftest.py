from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.auth.models import User
from app.auth.security import hash_password
from app.core.database import Base, get_db
from app.core.enums import BotPermissionStatus, UserRole
from app.main import app as fastapi_app
from app.models.refresh_token import RefreshToken  # noqa: F401 — register metadata
from app.schemas.queue import PublishQueueResponse
from app.telegram.client import BotPermissionsResult

DATABASE_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)
SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)


async def provision_test_user(
    *,
    email: str,
    password: str,
    full_name: str,
    role: UserRole | str,
) -> User:
    """Create a role-specific user directly in the test database."""
    async with SessionLocal() as session:
        user = User(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            role=UserRole(role),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def override_get_db() -> AsyncSession:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def init_app_dependency_overrides() -> None:
    fastapi_app.dependency_overrides[get_db] = override_get_db


class _AllowAllRateLimitRedis:
    """Default test Redis: counters never exceed any Task 0 limit."""

    async def incr(self, key: str) -> int:
        return 1

    async def expire(self, key: str, seconds: int) -> bool:
        return True

    async def ttl(self, key: str) -> int:
        return 300


@pytest.fixture(autouse=True)
def allow_all_rate_limit_redis(monkeypatch):
    """Keep existing API tests independent of a live Redis rate-limit counter."""

    async def _get_allow_all():
        return _AllowAllRateLimitRedis()

    monkeypatch.setattr("app.core.rate_limit.get_rate_limit_redis", _get_allow_all)


@pytest.fixture(scope="session", autouse=True)
async def prepare_database():
    init_app_dependency_overrides()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest.fixture
async def client():
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def session():
    async with SessionLocal() as db_session:
        yield db_session
        await db_session.rollback()


# External integration mock fixtures
@pytest.fixture
def mock_telegram_permissions(monkeypatch):
    """Mock TelegramBotClient.check_channel_permissions to return granted permissions."""
    async def fake_check_permissions(self, channel_id: str) -> BotPermissionsResult:
        return BotPermissionsResult(
            status=BotPermissionStatus.GRANTED,
            title="Test Channel",
            username="testchannel",
            can_post_messages=True,
            can_edit_messages=True,
            can_delete_messages=True,
            checked_at=datetime.now(UTC),
            detail="Bot has permissions",
        )

    monkeypatch.setattr(
        "app.services.channel.TelegramBotClient.check_channel_permissions",
        fake_check_permissions,
    )
    return fake_check_permissions


@pytest.fixture
def mock_ai_provider(monkeypatch):
    """Mock AI provider factory and URL fetcher for content generation tests."""
    async def fake_fetch(self, url: str) -> SimpleNamespace:
        return SimpleNamespace(
            url=url,
            title="Example Title",
            description="Example description",
            image_url="https://example.com/image.jpg",
        )

    class DummyAIProvider:
        name = "openai"

        @property
        def is_configured(self) -> bool:
            return True

        async def generate_content(self, prompt: str) -> str:
            return "هذا نص تسويقي باللغة العربية"

    monkeypatch.setattr(
        "app.services.ai_content.get_ai_provider",
        lambda provider=None: DummyAIProvider(),
    )
    monkeypatch.setattr(
        "app.services.ai_content.ProductURLFetcher.fetch",
        fake_fetch,
    )
    return DummyAIProvider(), fake_fetch


@pytest.fixture
def mock_queue_publish(monkeypatch):
    """Mock QueueService.publish to simulate successful Telegram publishing."""
    async def fake_publish(self, queue_id):
        return PublishQueueResponse(
            queue_id=queue_id,
            telegram_message_id=987654321,
            chat_id="@testchat",
            message_type="text",
            published_at=datetime.now(UTC),
        )

    monkeypatch.setattr("app.services.queue.QueueService.publish", fake_publish)
    return fake_publish


@pytest.fixture
def mock_telegram_publisher_success(monkeypatch):
    """Mock TelegramPublisher.publish success without bypassing QueueService."""
    from app.telegram.types import TelegramPublishResult

    calls: list[dict] = []

    async def fake_publish(
        self,
        chat_id,
        text,
        *,
        image_url=None,
        button=None,
        parse_mode=None,
    ):
        calls.append(
            {
                "chat_id": chat_id,
                "text": text,
                "image_url": image_url,
                "button": button,
                "parse_mode": parse_mode,
            }
        )
        return TelegramPublishResult(
            chat_id=str(chat_id),
            message_id=123456789,
            message_type="photo" if image_url else "text",
        )

    monkeypatch.setattr(
        "app.telegram.publisher.TelegramPublisher.publish",
        fake_publish,
    )
    return calls


@pytest.fixture
def mock_telegram_publisher_failure(monkeypatch):
    """Mock TelegramPublisher.publish to raise a transport failure."""
    from app.services.exceptions import TelegramPublishError

    calls: list[dict] = []

    async def fake_publish(
        self,
        chat_id,
        text,
        *,
        image_url=None,
        button=None,
        parse_mode=None,
    ):
        calls.append({"chat_id": chat_id, "text": text})
        raise TelegramPublishError(
            "Telegram transport failed",
            http_status=500,
            telegram_error_code=500,
        )

    monkeypatch.setattr(
        "app.telegram.publisher.TelegramPublisher.publish",
        fake_publish,
    )
    return calls
