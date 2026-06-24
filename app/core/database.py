from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# 1. Leave these empty on file initialization
_engine = None
_AsyncSessionLocal = None


class Base(DeclarativeBase):
    pass


def get_async_session_maker() -> async_sessionmaker[AsyncSession]:
    """Lazily initializes the engine and sessionmaker on first call."""
    global _engine, _AsyncSessionLocal
    
    if _AsyncSessionLocal is None:
        # 2. Moving this import inside the function breaks the circular import!
        from app.core.config import get_settings
        settings = get_settings()
        
        _engine = create_async_engine(
            str(settings.database_url),
            echo=settings.debug,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
        
        _AsyncSessionLocal = async_sessionmaker(
            bind=_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
        
    return _AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Dependency that yields the session."""
    session_maker = get_async_session_maker()
    
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise