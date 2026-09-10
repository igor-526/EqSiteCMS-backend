"""Frozen backfill/schema checks; real PostgreSQL constraints belong to QG-LIVE."""

import re
from importlib import import_module
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import String, UniqueConstraint

from models.news import news

migration = import_module("migration.versions.7d28fbc9a631_add_news_slug")


@pytest.mark.parametrize(
    ("name", "base"),
    [
        ("Ёж, щука и Юлия!", "yozh-schuka-i-yuliya"),
        ("  Конный -- КЛУБ  ", "konnyy-klub"),
        ("中文 🎠", "news"),
        ("___", "news"),
        ("", "news"),
        ("A" * 200, "a" * 127),
        ("a" * 126 + " - b", "a" * 126),
    ],
)
def test_frozen_slug_vectors(name: str, base: str) -> None:
    identity = UUID("12345678-9abc-def0-1234-56789abcdef0")
    slug = migration._generate_slug(name, identity)
    assert slug == f"{base}-{identity.hex}"
    assert len(slug) <= 160
    assert re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug)


def test_same_title_uses_full_uuid_to_disambiguate() -> None:
    left = UUID("12345678-0000-0000-0000-000000000001")
    right = UUID("12345678-0000-0000-0000-000000000002")
    assert migration._generate_slug("Новости", left) != migration._generate_slug(
        "Новости", right
    )


def test_schema_requires_bounded_slug_and_tenant_unique_constraint() -> None:
    assert news.c.slug.nullable is False
    assert isinstance(news.c.slug.type, String)
    assert news.c.slug.type.length == 160
    constraints = [
        constraint
        for constraint in news.constraints
        if isinstance(constraint, UniqueConstraint)
        and constraint.name == "uq_news_equestrian_slug"
    ]
    assert len(constraints) == 1
    assert list(constraints[0].columns.keys()) == ["equestrian_id", "slug"]


def test_upgrade_backfills_all_rows_before_constraints(monkeypatch) -> None:
    # SQL is captured, not executed against a substitute for PostgreSQL.
    rows = [
        {"id": UUID(int=1), "name": "Новости", "is_deleted": False},
        {"id": UUID(int=2), "name": "Новости", "is_deleted": True},
        {"id": UUID(int=3), "name": "中文", "published_at": "2099-01-01"},
    ]
    calls: list[tuple[Any, ...]] = []

    class Result:
        def mappings(self):
            return rows

    class Connection:
        def execute(self, statement, params=None):
            calls.append((str(statement), params))
            return Result()

    monkeypatch.setattr(migration.op, "get_bind", lambda: Connection())
    monkeypatch.setattr(
        migration.op,
        "add_column",
        lambda table, column: calls.append(("add", (table, column.nullable))),
    )
    monkeypatch.setattr(
        migration.op,
        "alter_column",
        lambda *args, **kwargs: calls.append(("alter", kwargs)),
    )
    monkeypatch.setattr(
        migration.op,
        "create_unique_constraint",
        lambda *args: calls.append(("unique", args)),
    )
    migration.upgrade()
    assert calls[0] == ("add", ("news", True))
    assert calls[1] == ("SELECT id, name FROM news", None)
    for row, call in zip(rows, calls[2:5], strict=True):
        assert call == (
            "UPDATE news SET slug = :slug WHERE id = :id",
            {
                "id": row["id"],
                "slug": migration._generate_slug(row["name"], row["id"]),
            },
        )
    assert calls[5][0] == "alter"
    assert calls[5][1]["nullable"] is False
    assert calls[6] == (
        "unique",
        ("uq_news_equestrian_slug", "news", ["equestrian_id", "slug"]),
    )
    assert len(calls) == 7


def test_downgrade_only_removes_slug_constraint_and_column(monkeypatch) -> None:
    calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        migration.op,
        "drop_constraint",
        lambda *args, **kwargs: calls.append(("constraint", args, kwargs)),
    )
    monkeypatch.setattr(
        migration.op,
        "drop_column",
        lambda *args: calls.append(("column", args)),
    )
    migration.downgrade()
    assert calls == [
        (
            "constraint",
            ("uq_news_equestrian_slug", "news"),
            {"type_": "unique"},
        ),
        ("column", ("news", "slug")),
    ]
