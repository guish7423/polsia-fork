"""Async database engine and session management."""

from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings
from app.models.base import Base


@lru_cache(maxsize=1)
def get_engine():
    """Return cached async engine (lazy init so tests can override DATABASE_URL)."""
    return create_async_engine(settings.database_url, echo=settings.debug)


@lru_cache(maxsize=1)
def get_async_session():
    """Return cached async sessionmaker."""
    return async_sessionmaker(
        get_engine(), class_=AsyncSession, expire_on_commit=False
    )

async_session = get_async_session()

async def get_db() -> AsyncSession:
    """Yield a database session with auto-commit on success, rollback on error."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """Create all tables from the ORM metadata (dev/test helper)."""
    from app.models.base import Base

    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
