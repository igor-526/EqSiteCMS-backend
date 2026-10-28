import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import event, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from maintain import provision_seo_smoke_user as command
from models.equestrian import equestrians
from models.users import user_scopes, user_scopes_relations, users
from settings import Settings
from utils.basemodel import metadata
from utils.security import Security

# Только фиктивный секрет, не локальные credentials.
TEST_PASSWORD = "synthetic-unit-test-secret"


@pytest.fixture
async def database():
    engine = create_async_engine("sqlite+aiosqlite://")
    lock = asyncio.Lock()
    lock_calls = []

    class LockedSession(AsyncSession):
        """Эмуляция только pg lock; SQL и rollback настоящие, на SQLite.

        Реальные advisory lock и PostgreSQL constraints проверяет SM-01, не unit.
        """

        @asynccontextmanager
        async def begin(self):
            self.has_lock = False
            try:
                async with super().begin():
                    yield self
            finally:
                if self.has_lock:
                    lock.release()

        async def execute(self, statement, params=None, **kwargs):
            if str(statement) == "SELECT pg_advisory_xact_lock(:key)":
                assert params == {"key": command.PROVISION_LOCK}
                lock_calls.append(params["key"])
                await lock.acquire()
                self.has_lock = True
                return None
            return await super().execute(statement, params, **kwargs)

    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync: metadata.create_all(
                sync, tables=[equestrians, users, user_scopes, user_scopes_relations]
            )
        )
    factory = async_sessionmaker(engine, class_=LockedSession)
    tenant = uuid4()
    async with factory() as session, session.begin():
        await session.execute(
            insert(equestrians).values(id=tenant, name="Test", service_key="fake-key")
        )
        await session.execute(
            insert(user_scopes).values(id=command.SEO_ID, scope_name="SEO")
        )
    yield factory, tenant, lock_calls, engine
    await engine.dispose()


async def snapshot(factory):
    async with factory() as session:
        account = (await session.execute(select(users))).mappings().all()
        relations = (
            (await session.execute(select(user_scopes_relations))).mappings().all()
        )
        return [dict(row) for row in account], [dict(row) for row in relations]


async def test_create_only_seo_and_noop_preserves_password(database):
    factory, tenant, calls, _ = database
    async with factory() as session:
        assert await command.provision(session, tenant, TEST_PASSWORD) == "created"
    before = await snapshot(factory)
    accounts, relations = before
    assert len(accounts) == len(relations) == 1
    account = accounts[0]
    assert account["username"] == "seo"
    assert account["equestrian_id"] == tenant
    assert not account["is_deleted"] and not account["is_blocked"]
    assert account["deleted_at"] is None
    assert account["password"] != TEST_PASSWORD
    assert Security().verify_password(TEST_PASSWORD, account["password"])
    assert relations[0]["scope_id"] == command.SEO_ID
    assert relations[0]["user_id"] == account["id"]
    async with factory() as session:
        assert (
            await command.provision(session, tenant, "different-fake-secret")
            == "unchanged"
        )
    assert await snapshot(factory) == before
    assert calls == [command.PROVISION_LOCK] * 2


@pytest.mark.parametrize(
    "conflict",
    ["tenant", "admin", "no_roles", "duplicate", "blocked", "deleted", "deleted_at"],
)
async def test_conflict_never_overwrites(database, conflict):
    factory, tenant, _, _ = database
    async with factory() as session:
        await command.provision(session, tenant, TEST_PASSWORD)
    accounts, relations = await snapshot(factory)
    user_id = accounts[0]["id"]
    async with factory() as session, session.begin():
        if conflict == "tenant":
            other = uuid4()
            await session.execute(
                insert(equestrians).values(
                    id=other, name="Other", service_key="other-key"
                )
            )
            await session.execute(update(users).values(equestrian_id=other))
        elif conflict == "admin":
            admin = uuid4()
            await session.execute(
                insert(user_scopes).values(id=admin, scope_name="ADMIN")
            )
            await session.execute(
                insert(user_scopes_relations).values(user_id=user_id, scope_id=admin)
            )
        elif conflict == "no_roles":
            # Только изолированная in-memory fixture, не runtime БД.
            await session.execute(user_scopes_relations.delete())
        elif conflict == "duplicate":
            await session.execute(
                insert(user_scopes_relations).values(
                    user_id=user_id, scope_id=command.SEO_ID
                )
            )
        elif conflict == "blocked":
            await session.execute(update(users).values(is_blocked=True))
        elif conflict == "deleted":
            await session.execute(update(users).values(is_deleted=True))
        else:
            from datetime import datetime, timezone

            await session.execute(
                update(users).values(deleted_at=datetime.now(timezone.utc))
            )
    before = await snapshot(factory)
    async with factory() as session:
        with pytest.raises(command.ProvisionError, match="несовместимой"):
            await command.provision(session, tenant, TEST_PASSWORD)
    assert await snapshot(factory) == before


async def test_assignment_error_rolls_back_user(database):
    factory, tenant, _, engine = database

    def fail_assignment(conn, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO user_scopes_relations"):
            raise RuntimeError("synthetic assignment failure")

    event.listen(engine.sync_engine, "before_cursor_execute", fail_assignment)
    try:
        async with factory() as session:
            with pytest.raises(RuntimeError, match="synthetic assignment"):
                await command.provision(session, tenant, TEST_PASSWORD)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", fail_assignment)
    assert await snapshot(factory) == ([], [])


async def test_concurrent_calls_one_user_and_relation(database):
    factory, tenant, calls, _ = database

    async def attempt():
        async with factory() as session:
            return await command.provision(session, tenant, TEST_PASSWORD)

    assert sorted(await asyncio.gather(attempt(), attempt())) == [
        "created",
        "unchanged",
    ]
    accounts, relations = await snapshot(factory)
    assert len(accounts) == len(relations) == 1
    assert calls == [command.PROVISION_LOCK] * 2


async def test_missing_tenant_and_conflicting_seed_refuse_without_writes(database):
    factory, tenant, _, _ = database
    async with factory() as session:
        with pytest.raises(command.ProvisionError, match="конюшня"):
            await command.provision(session, uuid4(), TEST_PASSWORD)
    async with factory() as session, session.begin():
        await session.execute(update(user_scopes).values(id=uuid4()))
    async with factory() as session:
        with pytest.raises(command.ProvisionError, match="seed"):
            await command.provision(session, tenant, TEST_PASSWORD)
    assert await snapshot(factory) == ([], [])


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["--confirm-local-test-db"],
        ["--equestrian-id", str(uuid4())],
        ["--password", "fake"],
    ],
)
def test_required_cli_parameters_stop_before_run(argv, monkeypatch):
    monkeypatch.setattr(command, "run", lambda _: pytest.fail("DB must not be opened"))
    with pytest.raises(SystemExit) as exc:
        command.main(argv)
    assert exc.value.code == 2


@pytest.mark.parametrize(
    "environment,host,confirmed",
    [
        ("production", "localhost", True),
        ("development", "external-db", True),
        ("development", "localhost", False),
    ],
)
def test_nonlocal_environment_rejected(environment, host, confirmed):
    config = Settings.model_construct(environment=environment, db_host=host)
    with pytest.raises(command.ProvisionError):
        command.validate_local_environment(config, confirmed)


async def test_run_preflight_rejects_before_engine_creation(monkeypatch):
    import argparse

    import sqlalchemy.ext.asyncio

    def forbidden_engine(*args, **kwargs):
        pytest.fail("DB engine must not be created")

    monkeypatch.setattr(sqlalchemy.ext.asyncio, "create_async_engine", forbidden_engine)
    monkeypatch.setattr(
        command,
        "settings",
        Settings.model_construct(environment="development", db_host="localhost"),
    )
    args = argparse.Namespace(
        equestrian_id=uuid4(), confirm_local_test_db=False, credentials=[]
    )
    with pytest.raises(command.ProvisionError, match="локальная"):
        await command.run(args)
    args.confirm_local_test_db = True
    with pytest.raises(command.ProvisionError, match="расходятся"):
        await command.run(args)


def test_password_ref_resolution_and_invalid_chains():
    roles = {
        "seo": {"login": "seo", "password_ref": "admin"},
        "admin": {"password_ref": "source"},
        "source": {"password": TEST_PASSWORD},
    }
    assert command.resolve_password(roles, "seo") == TEST_PASSWORD
    for invalid in [
        {"seo": {"password_ref": "missing"}},
        {"seo": {"password_ref": "admin"}, "admin": {"password_ref": "seo"}},
        {"seo": {}},
        {"seo": {"password": TEST_PASSWORD, "password_ref": "admin"}},
        {"seo": {"password_ref": []}},
    ]:
        with pytest.raises(command.ProvisionError):
            command.resolve_password(invalid, "seo")


def test_two_credentials_agreement_and_preservation(tmp_path):
    files = [tmp_path / "first.json", tmp_path / "second.json"]
    for index, path in enumerate(files):
        path.write_text(
            json.dumps(
                {
                    "base_url": f"http://local-{index}",
                    "roles": {
                        "seo": {"login": "seo", "password_ref": "admin"},
                        "admin": {"password": TEST_PASSWORD},
                    },
                }
            )
        )
    before = [path.read_bytes() for path in files]
    assert command.read_smoke_password(files) == TEST_PASSWORD
    assert before == [path.read_bytes() for path in files]
    other = json.loads(files[1].read_text())
    other["roles"]["admin"]["password"] = "different-fake-secret"
    files[1].write_text(json.dumps(other))
    with pytest.raises(command.ProvisionError, match="расходятся"):
        command.read_smoke_password(files)


def test_cli_failure_output_is_redacted(monkeypatch, capsys):
    async def fail(_):
        raise RuntimeError(TEST_PASSWORD)

    monkeypatch.setattr(command, "run", fail)
    assert (
        command.main(
            [
                "--equestrian-id",
                str(uuid4()),
                "--confirm-local-test-db",
                "--credentials",
                "first.json",
                "second.json",
            ]
        )
        == 1
    )
    assert TEST_PASSWORD not in capsys.readouterr().out


def test_both_skill_copies_use_local_ref_and_separate_cookie_jars():
    root = Path(__file__).resolve().parents[5]
    for copy in (".agents", ".claude"):
        instructions = (root / copy / "skills/api-smoke-test/SKILL.md").read_text()
        assert f"{copy}/skills/api-smoke-test/credentials.json" in instructions
        assert "password_ref=admin" in instructions
        assert ".qa/105-seo-role/<role>.cookies" in instructions
        assert "visited" in instructions and "цикл" in instructions
