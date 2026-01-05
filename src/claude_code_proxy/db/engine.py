"""Database engine and session management."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlmodel import SQLModel


# Default database path (using ~/.claude as the config directory)
DEFAULT_DB_PATH = Path("~/.claude").expanduser() / "proxy.db"

# Global engine (initialized on startup)
_engine = None
_async_session_maker = None


def get_db_url(path: Path | None = None) -> str:
    """Get SQLite database URL."""
    db_path = path or DEFAULT_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite+aiosqlite:///{db_path}"


async def init_db(path: Path | None = None) -> None:
    """Initialize database and create tables."""
    global _engine, _async_session_maker

    db_url = get_db_url(path)
    _engine = create_async_engine(db_url, echo=False)
    _async_session_maker = async_sessionmaker(
        _engine, class_=AsyncSession, expire_on_commit=False
    )

    async with _engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


def get_engine() -> AsyncEngine:
    """Get the database engine."""
    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _engine


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session."""
    if _async_session_maker is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")

    async with _async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
