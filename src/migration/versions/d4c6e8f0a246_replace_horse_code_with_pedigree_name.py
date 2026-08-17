"""replace horse code with pedigree name

Revision ID: d4c6e8f0a246
Revises: a1b2c3d4e5f6
Create Date: 2026-08-17 00:00:00.000000

This migration is intentionally lossy: existing horse.code values are not copied.
The downgrade restores only the old schema, not the discarded values.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4c6e8f0a246"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("horse", "code")
    op.add_column(
        "horse", sa.Column("pedigree_name", sa.String(length=63), nullable=True)
    )


def downgrade() -> None:
    """Restore the old structure; previously discarded code values stay lost."""
    op.drop_column("horse", "pedigree_name")
    op.add_column("horse", sa.Column("code", sa.String(length=31), nullable=True))
