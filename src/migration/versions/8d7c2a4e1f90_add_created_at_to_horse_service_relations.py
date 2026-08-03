"""add created_at to horse service relations

Revision ID: 8d7c2a4e1f90
Revises: 4c8f9a2d6e10
Create Date: 2026-08-03 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8d7c2a4e1f90"
down_revision: str | None = "4c8f9a2d6e10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "horse_service_relations",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
    )
    op.execute(
        sa.text(
            "UPDATE horse_service_relations "
            "SET created_at = now() WHERE created_at IS NULL"
        )
    )
    op.alter_column(
        "horse_service_relations",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )


def downgrade() -> None:
    op.drop_column("horse_service_relations", "created_at")
