import asyncio
import datetime
import json
import logging
import os
import random
from core.entities.horse import Horse, HorseDateModeEnum, HorseKindEnum, HorseSexEnum
from repositories import BreedRepository, CoatColorRepository, HorseOwnerRepository, HorseRepository
from utils.database import get_db
from core.entities import Breed, CoatColor, HorseOwner


async def generate_horses(
    horse_owner_repository: HorseOwnerRepository,
    breed_repository: BreedRepository,
    coat_color_repository: CoatColorRepository,
    horse_repository: HorseRepository,
):
    with open(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"),
        "r",
        encoding="utf-8",
    ) as f:
        config = json.load(f)
        HORSE_SEEDS: list[Horse] = []
        breeds: list[Breed] = await breed_repository.get_all()
        coat_colors: list[CoatColor] = await coat_color_repository.get_all()
        owners: list[HorseOwner] = await horse_owner_repository.get_all()
        horse_names: list[str] = config["horse_names"]
        horse_descriptions: list[str] = config["horse_descriptions"]
        for horse_name in horse_names:
            horse_age = random.randint(1, 25)
            is_dead = random.choice([True, False])
            dead_ago = random.randint(1, 100)
            if is_dead:
                ddate = datetime.datetime.now() - datetime.timedelta(days=dead_ago * 365)
                bdate = ddate - datetime.timedelta(days=horse_age * 365)
            else:
                bdate = datetime.datetime.now() - datetime.timedelta(days=horse_age * 365)
                ddate = None
            HORSE_SEEDS.append(Horse(
                name=horse_name,
                description=random.choice(horse_descriptions),
                breed_id=random.choice(breeds).id if breeds else None,
                coat_color_id=random.choice(coat_colors).id if coat_colors else None,
                kind=random.choice(list(HorseKindEnum)),
                height=random.randint(130, 200),
                sex=random.choice(list(HorseSexEnum)),
                bdate=bdate.date(),
                ddate=ddate.date() if ddate else None,
                bdate_mode=random.choice(list(HorseDateModeEnum)),
                ddate_mode=random.choice(list(HorseDateModeEnum)),
                horse_owner_id=random.choice(owners).id if owners else None,
                this_stable=random.choice([True, False]),
            ))
        await horse_repository.bulk_create(HORSE_SEEDS)
            


async def main():
    async with get_db() as session:
        horse_owner_repository = HorseOwnerRepository(session=session)
        breed_repository = BreedRepository(session=session)
        coat_color_repository = CoatColorRepository(session=session)
        horse_repository = HorseRepository(session=session)
        await generate_horses(
            horse_owner_repository=horse_owner_repository,
            breed_repository=breed_repository,
            coat_color_repository=coat_color_repository,
            horse_repository=horse_repository,
        )

    await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
