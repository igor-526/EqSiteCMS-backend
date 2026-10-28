from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.entities import UserScope
from core.seeds.user_scopes import USER_SCOPES_SEEDS
from models import user_scopes
from utils.seeding.seeders.simple_seeder import SimpleSeeder


class UserScopesSeeder(SimpleSeeder[UserScope]):
    """Seeds user scopes."""

    table = user_scopes
    entity_cls = UserScope
    seeds = USER_SCOPES_SEEDS

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def prepare(self) -> list[UserScope]:
        # Не заменять чужую роль/назначения при коллизии имени или seed UUID.
        seo = next(seed for seed in self.seeds if seed.scope_name == "SEO")
        rows = await self.session.execute(
            select(user_scopes.c.id, user_scopes.c.scope_name).where(
                (user_scopes.c.scope_name == "SEO") | (user_scopes.c.id == seo.id)
            )
        )
        if any(
            row["id"] != seo.id or row["scope_name"] != "SEO"
            for row in rows.mappings().all()
        ):
            raise RuntimeError("SEO seed conflict; operator intervention required")
        return await super().prepare()
