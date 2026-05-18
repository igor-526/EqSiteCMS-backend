"""horse kind to breed

Revision ID: 7a9d3e2f1c4b
Revises: c1e4d2a3b5f7
Create Date: 2026-05-18 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7a9d3e2f1c4b"
down_revision: str | None = "c1e4d2a3b5f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "breeds",
        sa.Column(
            "kind",
            sa.String(length=7),
            nullable=False,
            server_default="horse",
        ),
    )

    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                row_number() OVER (
                    PARTITION BY equestrian_id
                    ORDER BY random()
                ) AS rn,
                count(*) OVER (PARTITION BY equestrian_id) AS total
            FROM breeds
        )
        UPDATE breeds
        SET kind = 'pony'
        FROM ranked
        WHERE breeds.id = ranked.id
          AND ranked.rn <= floor(ranked.total / 2.0)
        """
    )

    op.create_index(
        "ix_breeds_equestrian_kind",
        "breeds",
        ["equestrian_id", "kind"],
        unique=False,
    )
    op.drop_index("ix_horse_equestrian_kind", table_name="horse")
    op.drop_column("horse", "kind")
    op.alter_column("breeds", "kind", server_default=None)


def downgrade() -> None:
    op.add_column(
        "horse",
        sa.Column(
            "kind",
            sa.String(length=7),
            nullable=False,
            server_default="horse",
        ),
    )
    op.execute(
        """
        UPDATE horse
        SET kind = COALESCE(breeds.kind, 'horse')
        FROM breeds
        WHERE horse.breed_id = breeds.id
          AND horse.equestrian_id = breeds.equestrian_id
        """
    )
    op.create_index(
        "ix_horse_equestrian_kind",
        "horse",
        ["equestrian_id", "kind"],
        unique=False,
    )
    op.drop_index("ix_breeds_equestrian_kind", table_name="breeds")
    op.drop_column("breeds", "kind")
