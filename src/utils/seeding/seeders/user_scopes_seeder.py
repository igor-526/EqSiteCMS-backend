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
