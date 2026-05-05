from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from core.protocols.security import SecurityProtocol
from settings import settings
from utils.database import AsyncSessionLocal
from utils.security import Security


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    session: AsyncSession = AsyncSessionLocal()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_security() -> SecurityProtocol:
    return Security()
