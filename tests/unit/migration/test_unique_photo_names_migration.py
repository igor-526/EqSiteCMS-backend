from __future__ import annotations

from datetime import datetime, timezone
from importlib import import_module
from typing import Any
from uuid import UUID

import pytest

migration = import_module("migration.versions.f3a1c7d9e245_unique_photo_names")


def row(id_value: int, tenant: int, name: str, created_at: datetime | None = None):
    return {
        "id": UUID(int=id_value),
        "equestrian_id": UUID(int=tenant),
        "name": name,
        "created_at": created_at,
    }


def test_clean_rows_need_no_renames() -> None:
    assert (
        migration._plan_duplicate_renames(
            [row(1, 10, "one.jpg"), row(2, 10, "two.jpg")]
        )
        == []
    )


def test_duplicate_keeper_is_first_in_migration_order() -> None:
    now = datetime.now(timezone.utc)
    rows = [row(1, 10, "photo.jpg", now), row(2, 10, "photo.jpg", None)]
    assert migration._plan_duplicate_renames(rows) == [(UUID(int=2), "photo-2.jpg")]


def test_reserved_suffix_is_not_overwritten() -> None:
    rows = [
        row(1, 10, "photo.jpg"),
        row(2, 10, "photo.jpg"),
        row(3, 10, "photo-2.jpg"),
    ]
    assert migration._plan_duplicate_renames(rows) == [(UUID(int=2), "photo-3.jpg")]


def test_long_stem_is_rebudgeted_for_suffix() -> None:
    name = "a" * 59 + ".jpg"
    renamed = migration._plan_duplicate_renames([row(1, 10, name), row(2, 10, name)])[
        0
    ][1]
    assert renamed.endswith("-2.jpg")
    assert len(renamed) == 63


def test_names_are_scoped_per_tenant() -> None:
    rows = [row(1, 10, "photo.jpg"), row(2, 11, "photo.jpg")]
    assert migration._plan_duplicate_renames(rows) == []


def test_downgrade_documents_irreversible_rename() -> None:
    assert "intentionally does not reverse" in (migration.__doc__ or "")


def test_post_check_failure_aborts_before_schema_change(monkeypatch) -> None:
    class Result:
        def mappings(self):
            return []

    class Connection:
        scalar_calls = 0

        def execute(self, *_args, **_kwargs):
            return Result()

        def scalar(self, *_args, **_kwargs):
            self.scalar_calls += 1
            return 1 if self.scalar_calls == 1 else 0

    dropped: list[str] = []
    monkeypatch.setattr(migration.op, "get_bind", lambda: Connection())
    monkeypatch.setattr(migration.op, "execute", lambda *_args: None)
    monkeypatch.setattr(
        migration.op, "drop_index", lambda name, **_kwargs: dropped.append(name)
    )
    with pytest.raises(RuntimeError, match="post-check failed"):
        migration.upgrade()
    assert dropped == []


def test_downgrade_restores_non_unique_index_without_data_updates(monkeypatch) -> None:
    calls: list[tuple[str, Any]] = []
    monkeypatch.setattr(
        migration.op,
        "drop_constraint",
        lambda name, *_args, **_kwargs: calls.append(("drop", name)),
    )
    monkeypatch.setattr(
        migration.op,
        "create_index",
        lambda name, *_args, **kwargs: calls.append(("index", (name, kwargs))),
    )
    migration.downgrade()
    assert calls[0] == ("drop", "uq_photos_equestrian_name")
    assert calls[1][0] == "index"
    assert calls[1][1][1]["unique"] is False
