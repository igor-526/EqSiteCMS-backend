from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Table,
    Text,
    text,
)

from utils.basemodel import metadata, soft_delete_columns, timestamp_columns, uuid_pk

news = Table(
    "news",
    metadata,
    uuid_pk(),
    *timestamp_columns(),
    Column(
        "equestrian_id",
        ForeignKey("equestrians.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("name", String(63), nullable=False),
    Column("snippet", String(255), nullable=True),
    Column("content", Text(), nullable=False, server_default=text("''")),
    Column("published_at", DateTime(timezone=True), nullable=False),
    *soft_delete_columns(),
    Index("ix_news_equestrian_id", "equestrian_id"),
    Index("ix_news_published_at", "published_at"),
    Index("ix_news_is_deleted", "is_deleted"),
)

news_photos = Table(
    "news_photos",
    metadata,
    uuid_pk(),
    Column("news_id", ForeignKey("news.id", ondelete="CASCADE"), nullable=False),
    Column("photo_id", ForeignKey("photos.id", ondelete="CASCADE"), nullable=False),
    Column("is_main", Boolean(), nullable=False, server_default=text("false")),
    Index("ix_news_photos_news_id", "news_id"),
    Index("ix_news_photos_photo_id", "photo_id"),
)
