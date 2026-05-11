"""Add news and news_photos tables.

Revision ID: e1a5f2b8c319
Revises: b3e7a2f91c04
Create Date: 2026-05-11 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1a5f2b8c319"
down_revision: Union[str, Sequence[str], None] = "b3e7a2f91c04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "news",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "equestrian_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("equestrians.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(63), nullable=False),
        sa.Column("snippet", sa.String(255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_news_equestrian_id", "news", ["equestrian_id"])
    op.create_index("ix_news_published_at", "news", ["published_at"])
    op.create_index("ix_news_is_deleted", "news", ["is_deleted"])

    op.create_table(
        "news_photos",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "news_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("news.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "photo_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("photos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "is_main",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index("ix_news_photos_news_id", "news_photos", ["news_id"])
    op.create_index("ix_news_photos_photo_id", "news_photos", ["photo_id"])


def downgrade() -> None:
    op.drop_index("ix_news_photos_photo_id", table_name="news_photos")
    op.drop_index("ix_news_photos_news_id", table_name="news_photos")
    op.drop_table("news_photos")
    op.drop_index("ix_news_is_deleted", table_name="news")
    op.drop_index("ix_news_published_at", table_name="news")
    op.drop_index("ix_news_equestrian_id", table_name="news")
    op.drop_table("news")
