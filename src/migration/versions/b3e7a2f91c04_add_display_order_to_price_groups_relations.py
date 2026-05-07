"""Add display_order to price_groups_relations.

Revision ID: b3e7a2f91c04
Revises: 9f0f2c5c7b11
Create Date: 2026-05-07 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b3e7a2f91c04"
down_revision: Union[str, Sequence[str], None] = "9f0f2c5c7b11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Добавляем колонку
    op.add_column(
        "price_groups_relations",
        sa.Column("display_order", sa.Integer(), nullable=True),
    )
    # Создаём partial unique index (NULL-значения не включаются в уникальный индекс)
    op.create_index(
        "uix_price_groups_relations_group_order",
        "price_groups_relations",
        ["group_id", "display_order"],
        unique=True,
        postgresql_where=sa.text("display_order IS NOT NULL"),
    )
    # Backfill: присваиваем существующим строкам display_order через двухфазный UPDATE
    # Фаза 1: уже NULL, ничего делать не надо
    # Фаза 2: назначаем ROW_NUMBER по group_id
    op.execute(
        """
        UPDATE price_groups_relations pgr
        SET display_order = sub.rn
        FROM (
            SELECT id,
                   ROW_NUMBER() OVER (PARTITION BY group_id ORDER BY id) AS rn
            FROM price_groups_relations
        ) sub
        WHERE pgr.id = sub.id
    """
    )


def downgrade() -> None:
    op.drop_index(
        "uix_price_groups_relations_group_order", table_name="price_groups_relations"
    )
    op.drop_column("price_groups_relations", "display_order")
