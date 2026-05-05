from sqlalchemy import Column, ForeignKey, Integer, String, Table, Text

from utils.basemodel import metadata, timestamp_columns, uuid_pk

horse_service = Table(
    "horse_service",
    metadata,
    uuid_pk(),
    *timestamp_columns(),
    Column("name", String(63), nullable=False, unique=True, index=True),
    Column("slug", String(63), nullable=False, index=True),
    Column("description", String(511), nullable=True),
    Column("price", Integer(), nullable=False),
    Column("price_formatter", String(7), nullable=False),
    Column("page_data", Text(), nullable=False, default="<div></div>"),
)

horse_service_relations = Table(
    "horse_service_relations",
    metadata,
    uuid_pk(),
    Column("horse_id", ForeignKey("horse.id", ondelete="CASCADE"), nullable=False),
    Column(
        "service_id", ForeignKey("horse_service.id", ondelete="CASCADE"), nullable=False
    ),
    Column("description_override", String(511), nullable=True),
    Column("price_override", Integer(), nullable=True),
    Column("price_formatter_override", String(7), nullable=True),
)
