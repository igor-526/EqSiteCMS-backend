"""

Revision ID: a1b2c3d4e5f6
Revises: f66b6991fb39
Create Date: 2026-08-14 10:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "8d7c2a4e1f90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add soft-delete and block fields to users table."""
    op.add_column(
        "users",
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Флаг мягкого удаления",
        ),
    )

    op.add_column(
        "users",
        sa.Column(
            "deleted_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Время мягкого удаления",
        ),
    )

    op.add_column(
        "users",
        sa.Column(
            "is_blocked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Флаг блокировки пользователя",
        ),
    )

    op.create_index(op.f("ix_users_is_deleted"), "users", ["is_deleted"], unique=False)
    op.create_index(op.f("ix_users_is_blocked"), "users", ["is_blocked"], unique=False)


def downgrade() -> None:
    """Remove soft-delete and block fields from users table."""
    op.drop_index(op.f("ix_users_is_blocked"), table_name="users")
    op.drop_index(op.f("ix_users_is_deleted"), table_name="users")
    op.drop_column("users", "is_blocked")
    op.drop_column("users", "deleted_at")
    op.drop_column("users", "is_deleted")
