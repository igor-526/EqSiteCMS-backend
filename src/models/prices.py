from sqlalchemy import Boolean, Column, ForeignKey, String, Table, Text, text
from sqlalchemy.dialects.postgresql import JSONB

from utils.basemodel import metadata, timestamp_columns, uuid_pk

prices = Table(
    "prices",
    metadata,
    uuid_pk(),
    *timestamp_columns(),
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
)

price_groups = Table(
    "price_groups",
    metadata,
    uuid_pk(),
    *timestamp_columns(),
    Column("name", String(63), nullable=False, index=True),
    Column("description", String(511), nullable=True),
)

price_groups_relations = Table(
    "price_groups_relations",
    metadata,
    uuid_pk(),
    Column("price_id", ForeignKey("prices.id", ondelete="CASCADE"), nullable=False),
    Column(
        "group_id", ForeignKey("price_groups.id", ondelete="CASCADE"), nullable=False
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
