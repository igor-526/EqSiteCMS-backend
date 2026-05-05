import asyncio
import random
from uuid import UUID
from repositories import HorseRepository, HorseChildrenRepository
from utils.database import get_db


async def generate_pedigree(
    horse_repository: HorseRepository,
    horse_children_repository: HorseChildrenRepository,
):
    all_horses = await horse_repository.get_all()
    for i, horse in enumerate(all_horses):
        print(f"({i+1}/{len(all_horses)}) Generating pedigree for {horse.name}...")
        foals_count = random.randint(3, 5)
        foals = await horse_repository.get_available_children(
            target_horse=horse,
        )
        if not foals[0]:
            print(f"No foals found for {horse.name}, skipping...")
            continue
        foals_ids: list[UUID] = [random.choice(list(foals[0].keys())) for _ in range(foals_count)]
        foals_ids = list(set(foals_ids))
        await horse_children_repository.set_pedigree(
            target_horse_id=horse.id,
            foals_ids=foals_ids,
        )


async def main():
    async with get_db() as session:
        horse_children_repository = HorseChildrenRepository(session=session)
        horse_repository = HorseRepository(session=session)
        await generate_pedigree(
            horse_children_repository=horse_children_repository,
            horse_repository=horse_repository,
        )

    await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
