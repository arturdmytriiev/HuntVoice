"""Database session management for Voice AI Restaurant Bot."""

import os
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool


# Database URL from environment variable
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/huntvoice",
)

# Ensure async driver is used
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)


class DatabaseConfig:
    """Database configuration settings."""

    # Connection pool settings
    POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "5"))
    MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    POOL_TIMEOUT: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "3600"))
    POOL_PRE_PING: bool = os.getenv("DB_POOL_PRE_PING", "true").lower() == "true"

    # Query settings
    ECHO: bool = os.getenv("DB_ECHO", "false").lower() == "true"
    ECHO_POOL: bool = os.getenv("DB_ECHO_POOL", "false").lower() == "true"

    # Connection settings
    CONNECT_ARGS: dict = {
        "server_settings": {
            "application_name": "huntvoice_bot",
        },
        "command_timeout": 60,
        "timeout": 10,
    }


def create_engine(
    url: str = DATABASE_URL,
    pool_size: int = DatabaseConfig.POOL_SIZE,
    max_overflow: int = DatabaseConfig.MAX_OVERFLOW,
    echo: bool = DatabaseConfig.ECHO,
) -> AsyncEngine:
    """
    Create async SQLAlchemy engine.

    Args:
        url: Database URL
        pool_size: Number of connections to maintain in pool
        max_overflow: Max number of connections to create beyond pool_size
        echo: Whether to log all SQL statements

    Returns:
        Async SQLAlchemy engine
    """
    return create_async_engine(
        url,
        echo=echo,
        echo_pool=DatabaseConfig.ECHO_POOL,
        poolclass=AsyncAdaptedQueuePool,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=DatabaseConfig.POOL_TIMEOUT,
        pool_recycle=DatabaseConfig.POOL_RECYCLE,
        pool_pre_ping=DatabaseConfig.POOL_PRE_PING,
        connect_args=DatabaseConfig.CONNECT_ARGS,
    )


def create_test_engine(url: str = DATABASE_URL) -> AsyncEngine:
    """
    Create async engine for testing with NullPool.

    Args:
        url: Database URL

    Returns:
        Async SQLAlchemy engine with NullPool
    """
    return create_async_engine(
        url,
        echo=False,
        poolclass=NullPool,
        connect_args=DatabaseConfig.CONNECT_ARGS,
    )


# Global engine instance
engine: AsyncEngine = create_engine()

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting async database session.

    Yields:
        AsyncSession instance

    Example:
        async def my_view(session: AsyncSession = Depends(get_session)):
            # use session
            pass
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_session_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for getting async database session.

    Yields:
        AsyncSession instance

    Example:
        async with get_session_context() as session:
            # use session
            pass
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database by creating all tables."""
    from .base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_db() -> None:
    """Drop all database tables. Use with caution!"""
    from .base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def close_db() -> None:
    """Close database engine and all connections."""
    await engine.dispose()
