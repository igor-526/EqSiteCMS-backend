"""add horse code

Revision ID: 4c8f9a2d6e10
Revises: 7a9d3e2f1c4b
Create Date: 2026-08-02 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4c8f9a2d6e10"
down_revision: str | None = "7a9d3e2f1c4b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("horse", sa.Column("code", sa.String(length=31), nullable=True))


def downgrade() -> None:
    op.drop_column("horse", "code")
