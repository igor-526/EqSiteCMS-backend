import asyncio
import json
import logging
import os
from repositories import BreedRepository, CoatColorRepository, HorseOwnerRepository
from utils.database import get_db
from core.entities import Breed, CoatColor, HorseOwner


async def seed_dev_horse_data(
    horse_owner_repository: HorseOwnerRepository,
    breed_repository: BreedRepository,
    coat_color_repository: CoatColorRepository,
):
    with open(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"),
        "r",
        encoding="utf-8",
    ) as f:
        config = json.load(f)
        HORSE_OWNERS_SEED: list[HorseOwner] = [
            HorseOwner(**horse_owner) for horse_owner in config["owners"]
        ]
        BREEDS_SEED: list[Breed] = [Breed(**breed) for breed in config["breeds"]]
        COAT_COLORS_SEED: list[CoatColor] = [
            CoatColor(**coat_color) for coat_color in config["coat_colors"]
        ]
        logging.info(f"Seeding {len(HORSE_OWNERS_SEED)} horse owners")
        await horse_owner_repository.bulk_create(HORSE_OWNERS_SEED)
        logging.info(f"Seeding {len(BREEDS_SEED)} breeds")
        await breed_repository.bulk_create(BREEDS_SEED)
        logging.info(f"Seeding {len(COAT_COLORS_SEED)} coat colors")
        await coat_color_repository.bulk_create(COAT_COLORS_SEED)
        logging.info("Seeding completed")


async def main():
    async with get_db() as session:
        horse_owner_repository = HorseOwnerRepository(session=session)
        breed_repository = BreedRepository(session=session)
        coat_color_repository = CoatColorRepository(session=session)

        await seed_dev_horse_data(
            horse_owner_repository=horse_owner_repository,
            breed_repository=breed_repository,
            coat_color_repository=coat_color_repository,
        )

    await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
