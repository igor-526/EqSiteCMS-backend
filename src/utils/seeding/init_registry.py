import asyncio
import logging
import os
from pathlib import Path
from typing import Callable

from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession

from utils.database import get_db
from utils.seeding.seeders import UserScopesSeeder
from utils.seeding.seeders.base_seeder import BaseSeeder

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = float(os.getenv("INIT_REGISTRY_TIMEOUT", "60"))
DEFAULT_MAX_ATTEMPTS = int(os.getenv("INIT_REGISTRY_MAX_ATTEMPTS", "5"))
DEFAULT_BACKOFF_SECONDS = float(os.getenv("INIT_REGISTRY_BACKOFF_SECONDS", "2"))


async def apply_migration(
    *,
    timeout: float = DEFAULT_TIMEOUT,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
) -> None:
    base_dir = Path(__file__).resolve().parents[2]

    for attempt in range(1, max_attempts + 1):
        alembic_config = Config(str(base_dir / "alembic.ini"))
        alembic_config.set_main_option("script_location", str(base_dir / "migration"))
        alembic_config.attributes["configure_logger"] = False
        try:
            await asyncio.wait_for(
                asyncio.to_thread(command.upgrade, alembic_config, "head"),
                timeout=timeout if timeout > 0 else None,
            )
            logger.info("Миграции успешно были применены.")
            return
        except Exception as exc:
            if attempt >= max_attempts:
                logger.error(
                    "Не удалось применить миграции после %s попыток: %s",
                    max_attempts,
                    exc,
                )
                raise

            wait_time = backoff_seconds * attempt if backoff_seconds > 0 else 0
            logger.warning(
                "Ошибка наката миграций (попытка %s из %s): %s. "
                "Повтор через %.1f секунд.",
                attempt,
                max_attempts,
                exc,
                wait_time,
            )
            if wait_time:
                await asyncio.sleep(wait_time)


async def run_seeders_with_retry(
    factory: Callable[[AsyncSession], list[BaseSeeder]],
    *,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
) -> None:
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            async with get_db() as session:
                logger.info("Starting seeding lifecycle...")
                seeders = factory(session)
                for seeder in seeders:
                    await seeder.run()
            logger.info("Сидирование завершено.")
            return
        except Exception as exc:
            last_error = exc
            if attempt >= max_attempts:
                logger.error(
                    "Сидирование не удалось после %s попыток: %s", max_attempts, exc
                )
                raise

            wait_time = backoff_seconds * attempt if backoff_seconds > 0 else 0
            logger.warning(
                "Ошибка сидирования (попытка %s из %s): %s. "
                "Повтор через %.1f секунд.",
                attempt,
                max_attempts,
                exc,
                wait_time,
            )
            if wait_time:
                await asyncio.sleep(wait_time)

    if last_error:
        raise last_error


def _build_seeders(session: AsyncSession) -> list[BaseSeeder]:
    return [UserScopesSeeder(session)]


async def init_registry() -> None:
    await apply_migration()
    await run_seeders_with_retry(_build_seeders)
