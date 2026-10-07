from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker as sync_sessionmaker
from sqlalchemy.pool import NullPool

from settings import settings

# Create async engine with pool configuration
# NullPool is used in debug mode to avoid connection pooling issues during development
if settings.debug:
    async_engine = create_async_engine(
        settings.database_url,
        future=True,
        poolclass=NullPool,
    )
else:
    async_engine = create_async_engine(
        settings.database_url,
        future=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_pre_ping=True,
        pool_recycle=settings.db_pool_recycle,
    )

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    expire_on_commit=False,
    autoflush=False,
)


sync_engine = create_engine(
    settings.sync_database_url,
    pool_size=5,
    max_overflow=10,
)

SyncSession = sync_sessionmaker(
    sync_engine,
    autocommit=False,
    autoflush=False,
)


def make_async_engine(url: str, *, use_null_pool: bool = True):
    return create_async_engine(
        url,
        future=True,
        poolclass=NullPool if use_null_pool else None,
    )


def make_async_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        engine,
        expire_on_commit=False,
        autoflush=False,
    )


@asynccontextmanager
async def get_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
