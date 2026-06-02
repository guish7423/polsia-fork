"""Async database engine and session management."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

engine = create_async_engine(settings.database_url, echo=settings.debug)
async_session = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


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

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Lightweight migrations for column additions
    async with engine.begin() as conn:
        # Trigger table creation for new models
        await conn.run_sync(Base.metadata.create_all)
        for col_sql in [
            "ALTER TABLE external_orders ADD COLUMN deliverables JSON",
            "ALTER TABLE external_orders ADD COLUMN delivery_notes TEXT",
        ]:
            try:
                await conn.execute(text(col_sql))
            except Exception:
                pass  # Column already exists

        # Create weekly_reports table (used by weekly report service)
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS weekly_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                period_start TEXT NOT NULL,
                period_end TEXT NOT NULL,
                summary TEXT,
                html_content TEXT,
                recipient_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """))
