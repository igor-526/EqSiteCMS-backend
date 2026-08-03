from __future__ import annotations

from importlib import import_module
from unittest.mock import call

import sqlalchemy as sa

migration = import_module(
    "migration.versions.8d7c2a4e1f90_add_created_at_to_horse_service_relations"
)


def test_ut01_upgrade_never_deletes_or_recreates_relation_rows(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        migration.op, "add_column", lambda *args, **kwargs: calls.append("add")
    )
    monkeypatch.setattr(
        migration.op, "execute", lambda *args, **kwargs: calls.append("execute")
    )
    monkeypatch.setattr(
        migration.op, "alter_column", lambda *args, **kwargs: calls.append("alter")
    )

    migration.upgrade()

    assert calls == ["add", "execute", "alter"]


def test_ut02_upgrade_backfills_only_null_created_at(monkeypatch) -> None:
    executed: list[sa.sql.elements.TextClause] = []
    monkeypatch.setattr(migration.op, "add_column", lambda *args, **kwargs: None)
    monkeypatch.setattr(migration.op, "execute", executed.append)
    monkeypatch.setattr(migration.op, "alter_column", lambda *args, **kwargs: None)

    migration.upgrade()

    assert str(executed[0]) == (
        "UPDATE horse_service_relations "
        "SET created_at = now() WHERE created_at IS NULL"
    )


def test_ut03_upgrade_finishes_with_not_null_server_default(monkeypatch) -> None:
    monkeypatch.setattr(migration.op, "add_column", lambda *args, **kwargs: None)
    monkeypatch.setattr(migration.op, "execute", lambda *args, **kwargs: None)
    alter_calls = []
    monkeypatch.setattr(
        migration.op,
        "alter_column",
        lambda *args, **kwargs: alter_calls.append((args, kwargs)),
    )

    migration.upgrade()

    args, kwargs = alter_calls[0]
    assert args == ("horse_service_relations", "created_at")
    assert kwargs["nullable"] is False
    assert str(kwargs["server_default"]) == "now()"


def test_ut04_downgrade_drops_only_created_at(monkeypatch) -> None:
    drop_column = []
    monkeypatch.setattr(
        migration.op, "drop_column", lambda *args: drop_column.append(call(*args))
    )

    migration.downgrade()

    assert drop_column == [call("horse_service_relations", "created_at")]
