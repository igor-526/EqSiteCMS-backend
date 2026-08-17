from importlib import import_module
from typing import Any
from unittest.mock import call

from sqlalchemy import String

migration = import_module(
    "migration.versions.d4c6e8f0a246_replace_horse_code_with_pedigree_name"
)


def test_upgrade_drops_code_then_adds_nullable_varchar_63(monkeypatch) -> None:
    calls: list[Any] = []
    monkeypatch.setattr(
        migration.op, "drop_column", lambda *args: calls.append(call("drop", *args))
    )
    monkeypatch.setattr(
        migration.op,
        "add_column",
        lambda table, column: calls.append(call("add", table, column)),
    )

    migration.upgrade()

    assert calls[0] == call("drop", "horse", "code")
    added = calls[1].args[2]
    assert calls[1].args[1] == "horse"
    assert added.name == "pedigree_name"
    assert added.nullable is True
    assert isinstance(added.type, String)
    assert added.type.length == 63


def test_downgrade_is_structural_and_documents_loss(monkeypatch) -> None:
    calls: list[Any] = []
    monkeypatch.setattr(
        migration.op, "drop_column", lambda *args: calls.append(call("drop", *args))
    )
    monkeypatch.setattr(
        migration.op,
        "add_column",
        lambda table, column: calls.append(call("add", table, column)),
    )

    migration.downgrade()

    assert calls[0] == call("drop", "horse", "pedigree_name")
    restored = calls[1].args[2]
    assert restored.name == "code"
    assert isinstance(restored.type, String)
    assert restored.type.length == 31
    assert "lost" in (migration.downgrade.__doc__ or "")
