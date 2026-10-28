from uuid import UUID, uuid4

import pytest
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from core.seeds.user_scopes import USER_SCOPES_SEEDS
from models.equestrian import equestrians
from models.users import user_scopes, user_scopes_relations, users
from utils.basemodel import metadata
from utils.seeding.seeders.user_scopes_seeder import UserScopesSeeder

LEGACY = {
    "SUPERUSER": ("4fe58c9e-e9bb-47d8-b4dc-655d9c59f74b", "Все права"),
    "ADMIN": ("3910a469-8955-416e-bd48-2771052b1605", "Администрирование сайта"),
    "DEVELOPER": (
        "5c5d5e56-3ab7-4077-a8a8-5e28dfeb0b54",
        "Администрирование сайта и настройка интеграции",
    ),
    "USER_MANAGER": (
        "7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b1c2d",
        "Управление пользователями",
    ),
}


def test_seed_parses_unique_stable_uuid_and_unchanged_legacy():
    assert len(USER_SCOPES_SEEDS) == 5
    assert len({seed.id for seed in USER_SCOPES_SEEDS}) == 5
    for seed in USER_SCOPES_SEEDS:
        assert isinstance(seed.id, UUID)
        if seed.scope_name == "SEO":
            assert seed.id.version == 4
            assert seed.scope_description == "Управление SEO"
        else:
            assert (str(seed.id), seed.scope_description) == LEGACY[seed.scope_name]


@pytest.fixture
async def database():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync: metadata.create_all(
                sync, tables=[equestrians, users, user_scopes, user_scopes_relations]
            )
        )
    yield async_sessionmaker(engine)
    await engine.dispose()


async def test_first_and_repeated_seed_preserve_ids_and_assignments(database):
    tenant, user = uuid4(), uuid4()
    seo = next(seed for seed in USER_SCOPES_SEEDS if seed.scope_name == "SEO")
    async with database() as session, session.begin():
        await UserScopesSeeder(session).run()
        await session.execute(
            insert(equestrians).values(id=tenant, name="Test", service_key="fake")
        )
        await session.execute(
            insert(users).values(
                id=user, equestrian_id=tenant, username="fixture", password="fake-hash"
            )
        )
        # Назначения как SEO, так и прежней роли сохраняются.
        await session.execute(
            insert(user_scopes_relations),
            [
                {"user_id": user, "scope_id": seo.id},
                {"user_id": user, "scope_id": USER_SCOPES_SEEDS[0].id},
            ],
        )
    async with database() as session, session.begin():
        before = (await session.execute(select(user_scopes_relations))).all()
        await UserScopesSeeder(session).run()
        assert (await session.execute(select(user_scopes_relations))).all() == before
        rows = (await session.execute(select(user_scopes))).mappings().all()
        assert {row["id"] for row in rows} == {seed.id for seed in USER_SCOPES_SEEDS}
        assert len(rows) == 5


@pytest.mark.parametrize("conflict", ["name", "id"])
async def test_seed_collision_is_safe_operator_blocker(database, conflict):
    seo = next(seed for seed in USER_SCOPES_SEEDS if seed.scope_name == "SEO")
    async with database() as session, session.begin():
        await session.execute(
            insert(user_scopes).values(
                id=uuid4() if conflict == "name" else seo.id,
                scope_name="SEO" if conflict == "name" else "FOREIGN",
            )
        )
    async with database() as session:
        before = (await session.execute(select(user_scopes))).all()
    async with database() as session:
        with pytest.raises(RuntimeError, match="SEO seed conflict"):
            async with session.begin():
                await UserScopesSeeder(session).run()
    async with database() as session:
        assert (await session.execute(select(user_scopes))).all() == before
