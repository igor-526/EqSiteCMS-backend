"""Явная локальная подготовка SEO smoke-пользователя (не startup seed).

Из services/backend: PYTHONPATH=src uv run python -m maintain.provision_seo_smoke_user
  --confirm-local-test-db --equestrian-id <UUID> --credentials <file1> <file2>
Оба credentials читаются в памяти; пароль и DSN не принимаются аргументами.
"""

import argparse
import asyncio
import json
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.seeds.user_scopes import USER_SCOPES_SEEDS
from models.equestrian import equestrians
from models.users import user_scopes, user_scopes_relations, users
from settings import Settings, settings
from utils.security import Security

SEO_ID = next(seed.id for seed in USER_SCOPES_SEEDS if seed.scope_name == "SEO")
# Общий ключ для username во всех tenants; блокировка снимается с транзакцией.
PROVISION_LOCK = 105_000_001


class ProvisionError(Exception):
    """Сообщение безопасно для CLI: без секретов и SQL-параметров."""


def resolve_password(roles: dict, role: str) -> str:
    """Разрешить password_ref только внутри переданного credentials файла."""
    visited = set()
    while True:
        if not isinstance(role, str) or role in visited or role not in roles:
            raise ProvisionError("Отсутствующий или циклический password_ref.")
        visited.add(role)
        entry = roles[role]
        if not isinstance(entry, dict):
            raise ProvisionError("Некорректный профиль credentials.")
        if "password_ref" in entry:
            if "password" in entry:
                raise ProvisionError("Неоднозначный источник пароля.")
            role = entry["password_ref"]
            continue
        password = entry.get("password")
        if not isinstance(password, str) or not password:
            raise ProvisionError("В credentials отсутствует пароль.")
        return password


def read_smoke_password(paths: list[Path]) -> str:
    passwords = []
    for path in paths:
        try:
            roles = json.loads(path.read_text(encoding="utf-8"))["roles"]
            if roles["seo"] != {"login": "seo", "password_ref": "admin"}:
                raise ProvisionError("Требуется SEO профиль с password_ref=admin.")
            password = resolve_password(roles, "seo")
            if password != resolve_password(roles, "admin"):
                raise ProvisionError("Пароли SEO и admin расходятся.")
            passwords.append(password)
        except (OSError, ValueError, KeyError, TypeError):
            raise ProvisionError(
                "Не удалось прочитать локальные credentials."
            ) from None
    if len(passwords) != 2 or passwords[0] != passwords[1]:
        raise ProvisionError("Пароли двух копий SMOKE расходятся; нужен оператор.")
    return passwords[0]


def validate_local_environment(config: Settings, confirmed: bool) -> None:
    if (
        not confirmed
        or config.environment.lower() not in {"development", "test", "local"}
        or config.db_host not in {"localhost", "127.0.0.1", "::1", "db", "eqsitecms-db"}
    ):
        raise ProvisionError("Требуется подтверждённая локальная тестовая PostgreSQL.")


async def provision(session: AsyncSession, equestrian_id: UUID, password: str) -> str:
    """Одна транзакция: lock → проверки → пользователь + единственная связь.

    Вызывать только с новой сессией. Совместимая запись не обновляется, в том
    числе её пароль. IntegrityError/любое исключение откатывает оба INSERT.
    """
    async with session.begin():
        await session.execute(
            text("SELECT pg_advisory_xact_lock(:key)"), {"key": PROVISION_LOCK}
        )
        tenant = await session.scalar(
            select(equestrians.c.id).where(equestrians.c.id == equestrian_id)
        )
        if tenant is None:
            raise ProvisionError("Выбранная тестовая конюшня не существует.")
        scopes = (
            (
                await session.execute(
                    select(user_scopes).where(
                        (user_scopes.c.scope_name == "SEO")
                        | (user_scopes.c.id == SEO_ID)
                    )
                )
            )
            .mappings()
            .all()
        )
        if len(scopes) != 1 or (
            scopes[0]["id"] != SEO_ID or scopes[0]["scope_name"] != "SEO"
        ):
            raise ProvisionError(
                "SEO seed отсутствует или конфликтует; нужен оператор."
            )
        existing = (
            (await session.execute(select(users).where(users.c.username == "seo")))
            .mappings()
            .one_or_none()
        )
        if existing is not None:
            assigned = (
                await session.scalars(
                    select(user_scopes_relations.c.scope_id).where(
                        user_scopes_relations.c.user_id == existing["id"]
                    )
                )
            ).all()
            if (
                existing["equestrian_id"] != equestrian_id
                or existing["is_deleted"]
                or existing["deleted_at"] is not None
                or existing["is_blocked"]
                or assigned != [SEO_ID]
            ):
                raise ProvisionError("Username seo занят несовместимой записью.")
            return "unchanged"
        user_id = uuid4()
        await session.execute(
            insert(users).values(
                id=user_id,
                equestrian_id=equestrian_id,
                username="seo",
                password=Security().hash_password(password),
                is_deleted=False,
                is_blocked=False,
            )
        )
        await session.execute(
            insert(user_scopes_relations).values(
                id=uuid4(), user_id=user_id, scope_id=SEO_ID
            )
        )
    return "created"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--equestrian-id", type=UUID, required=True)
    parser.add_argument("--confirm-local-test-db", action="store_true", required=True)
    parser.add_argument("--credentials", type=Path, nargs=2, required=True)
    return parser.parse_args(argv)


async def run(args: argparse.Namespace) -> str:
    validate_local_environment(settings, args.confirm_local_test_db)
    password = read_smoke_password(args.credentials)
    # Создаём engine только после всех локальных проверок; никаких DB startup hooks.
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(
        settings.database_url, echo=False, hide_parameters=True
    )
    try:
        async with async_sessionmaker(engine)() as session:
            return await provision(session, args.equestrian_id, password)
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = asyncio.run(run(args))
    except ProvisionError as exc:
        print(str(exc))
        return 1
    except Exception:
        # SQLAlchemy/asyncpg исключения могут содержать DSN, хеш и параметры SQL.
        print(
            "Подготовка отклонена; транзакция отменена. Проверьте локальное окружение."
        )
        return 1
    print(f"SEO smoke: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
