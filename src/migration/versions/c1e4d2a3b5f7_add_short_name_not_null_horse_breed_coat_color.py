"""add_short_name_not_null_horse_breed_coat_color

Revision ID: c1e4d2a3b5f7
Revises: e1a5f2b8c319
Create Date: 2026-05-15 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1e4d2a3b5f7"
down_revision: Union[str, Sequence[str], None] = "e1a5f2b8c319"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SHORT_NAME_MAX_LEN = 63


def upgrade() -> None:
    """Fill NULL short_name values from name, then add NOT NULL constraint."""

    # 1. Заполнить существующие NULL-значения short_name из поля name
    op.execute(
        sa.text(
            f"UPDATE breeds SET short_name = LEFT(name, {SHORT_NAME_MAX_LEN}) "
            "WHERE short_name IS NULL"
        )
    )
    op.execute(
        sa.text(
            f"UPDATE coat_color SET short_name = LEFT(name, {SHORT_NAME_MAX_LEN}) "
            "WHERE short_name IS NULL"
        )
    )

    # 2. Добавить NOT NULL constraint
    op.alter_column(
        "breeds",
        "short_name",
        existing_type=sa.String(length=63),
        nullable=False,
    )
    op.alter_column(
        "coat_color",
        "short_name",
        existing_type=sa.String(length=63),
        nullable=False,
    )


def downgrade() -> None:
    """Remove NOT NULL constraint (restore nullable=True)."""

    op.alter_column(
        "breeds",
        "short_name",
        existing_type=sa.String(length=63),
        nullable=True,
    )
    op.alter_column(
        "coat_color",
        "short_name",
        existing_type=sa.String(length=63),
        nullable=True,
    )
