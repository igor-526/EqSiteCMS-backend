from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB

from utils.basemodel import metadata, timestamp_columns, uuid_pk

prices = Table(
    "prices",
    metadata,
    uuid_pk(),
    *timestamp_columns(),
    Column(
        "equestrian_id",
        ForeignKey("equestrians.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("name", String(63), nullable=False, index=True),
    Column("description", String(511), nullable=True),
    Column("page_data", Text(), nullable=False, default="<div></div>"),
    Column("slug", String(63), nullable=False, index=True),
    Column(
        "price_tables",
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    ),
    Index("ix_prices_equestrian_slug", "equestrian_id", "slug", unique=True),
    Index("ix_prices_equestrian_name", "equestrian_id", "name"),
)

price_groups = Table(
    "price_groups",
    metadata,
    uuid_pk(),
    *timestamp_columns(),
    Column(
        "equestrian_id",
        ForeignKey("equestrians.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("name", String(63), nullable=False, index=True),
    Column("description", String(511), nullable=True),
    Index("ix_price_groups_equestrian_name", "equestrian_id", "name"),
)

price_groups_relations = Table(
    "price_groups_relations",
    metadata,
    uuid_pk(),
    Column("price_id", ForeignKey("prices.id", ondelete="CASCADE"), nullable=False),
    Column(
        "group_id", ForeignKey("price_groups.id", ondelete="CASCADE"), nullable=False
    ),
    Column("display_order", Integer, nullable=True),
    Index(
        "uix_price_groups_relations_group_order",
        "group_id",
        "display_order",
        unique=True,
        postgresql_where=text("display_order IS NOT NULL"),
    ),
)

price_photos = Table(
    "price_photos",
    metadata,
    uuid_pk(),
    Column("price_id", ForeignKey("prices.id", ondelete="CASCADE"), nullable=False),
    Column("photo_id", ForeignKey("photos.id", ondelete="CASCADE"), nullable=False),
    Column("is_main", Boolean(), nullable=False, default=False),
)
