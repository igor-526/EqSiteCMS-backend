"""make photo names unique within a tenant

Revision ID: f3a1c7d9e245
Revises: b6d4f8a21c03

Existing duplicate display names are renamed deterministically. Downgrade restores
the former non-unique index but intentionally does not reverse those safe renames.
"""

from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = "f3a1c7d9e245"
down_revision: str | None = "b6d4f8a21c03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MAX_NAME_LENGTH = 63


def _bounded_suffix(name: str, counter: int) -> str:
    dot_index = name.rfind(".")
    extension = name[dot_index:] if 0 < dot_index < len(name) - 1 else ""
    stem = name[:dot_index] if extension else name
    discriminator = f"-{counter}"
    budget = MAX_NAME_LENGTH - len(extension) - len(discriminator)
    return f"{(stem[:budget] or 'photo'[:budget])}{discriminator}{extension}"


def _plan_duplicate_renames(
    rows: Iterable[Mapping[str, Any]],
) -> list[tuple[UUID, str]]:
    ordered_rows = list(rows)
    reserved: dict[UUID, set[str]] = defaultdict(set)
    groups: dict[tuple[UUID, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in ordered_rows:
        tenant_id = row["equestrian_id"]
        name = row["name"]
        reserved[tenant_id].add(name)
        groups[(tenant_id, name)].append(row)

    renames: list[tuple[UUID, str]] = []
    for (tenant_id, name), duplicates in groups.items():
        if len(duplicates) < 2:
            continue
        for row in duplicates[1:]:
            counter = 2
            candidate = _bounded_suffix(name, counter)
            while candidate in reserved[tenant_id]:
                counter += 1
                candidate = _bounded_suffix(name, counter)
            reserved[tenant_id].add(candidate)
            renames.append((row["id"], candidate))
    return renames


def upgrade() -> None:
    connection = op.get_bind()
    op.execute(sa.text("LOCK TABLE photos IN SHARE ROW EXCLUSIVE MODE"))
    rows = connection.execute(
        sa.text(
            """
            SELECT id, equestrian_id, name, created_at
            FROM photos
            ORDER BY equestrian_id, name, created_at NULLS LAST, id
            """
        )
    ).mappings()
    renames = _plan_duplicate_renames(dict(row) for row in rows)
    for photo_id, name in renames:
        connection.execute(
            sa.text("UPDATE photos SET name = :name WHERE id = :id"),
            {"id": photo_id, "name": name},
        )

    duplicate_count = connection.scalar(
        sa.text(
            """
            SELECT count(*) FROM (
                SELECT 1 FROM photos
                GROUP BY equestrian_id, name HAVING count(*) > 1
            ) AS duplicate_groups
            """
        )
    )
    overlong_count = connection.scalar(
        sa.text("SELECT count(*) FROM photos WHERE char_length(name) > 63")
    )
    if duplicate_count or overlong_count:
        raise RuntimeError(
            "Photo name cleanup post-check failed: "
            f"duplicates={duplicate_count}, overlong={overlong_count}"
        )

    op.drop_index("ix_photos_equestrian_name", table_name="photos")
    op.create_unique_constraint(
        "uq_photos_equestrian_name", "photos", ["equestrian_id", "name"]
    )


def downgrade() -> None:
    # Cleanup renames are intentionally irreversible without an audit mapping.
    op.drop_constraint("uq_photos_equestrian_name", "photos", type_="unique")
    op.create_index(
        "ix_photos_equestrian_name",
        "photos",
        ["equestrian_id", "name"],
        unique=False,
    )
