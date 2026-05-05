import abc
import logging

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class BaseSeeder(abc.ABC):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def run(self) -> None:
        plan = await self.prepare()
        existing = await self.fetch_existing(plan)
        missing = self.diff(plan, existing)
        if missing:
            created = await self.create_missing(missing, plan, existing)
            logging.info(f"{self.__class__.__name__} created {created} entities")
            return
        logging.info(f"{self.__class__.__name__} created 0 entities")

    @abc.abstractmethod
    async def prepare(self): ...

    @abc.abstractmethod
    async def fetch_existing(self, plan): ...

    @abc.abstractmethod
    def diff(self, plan, existing): ...

    @abc.abstractmethod
    async def create_missing(self, missing, plan, existing) -> int: ...
