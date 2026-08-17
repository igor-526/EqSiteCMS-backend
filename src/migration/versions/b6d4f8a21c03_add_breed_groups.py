"""add breed groups

Revision ID: b6d4f8a21c03
Revises: d4c6e8f0a246
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b6d4f8a21c03"
down_revision: str | None = "d4c6e8f0a246"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "breed_groups",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("equestrian_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(63), nullable=False),
        sa.Column("slug", sa.String(63), nullable=False),
        sa.Column("page_data", sa.Text(), server_default="<div></div>", nullable=False),
        sa.ForeignKeyConstraint(
            ["equestrian_id"], ["equestrians.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "equestrian_id", "name", name="uq_breed_groups_equestrian_name"
        ),
    )
    op.create_index("ix_breed_groups_equestrian_id", "breed_groups", ["equestrian_id"])
    op.create_index(
        "ix_breed_groups_equestrian_slug",
        "breed_groups",
        ["equestrian_id", "slug"],
        unique=True,
    )
    op.add_column("breeds", sa.Column("breed_group_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_breeds_breed_group_id",
        "breeds",
        "breed_groups",
        ["breed_group_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_breeds_breed_group_id", "breeds", ["breed_group_id"])


def downgrade() -> None:
    op.drop_index("ix_breeds_breed_group_id", table_name="breeds")
    op.drop_constraint("fk_breeds_breed_group_id", "breeds", type_="foreignkey")
    op.drop_column("breeds", "breed_group_id")
    op.drop_index("ix_breed_groups_equestrian_slug", table_name="breed_groups")
    op.drop_index("ix_breed_groups_equestrian_id", table_name="breed_groups")
    op.drop_table("breed_groups")
