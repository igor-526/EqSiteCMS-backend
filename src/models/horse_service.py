from sqlalchemy import (
    Column,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)

from utils.basemodel import metadata, timestamp_columns, uuid_pk

horse_service = Table(
    "horse_service",
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
    Column("slug", String(63), nullable=False, index=True),
    Column("description", String(511), nullable=True),
    Column("price", Integer(), nullable=False),
    Column("price_formatter", String(7), nullable=False),
    Column("page_data", Text(), nullable=False, default="<div></div>"),
    UniqueConstraint("equestrian_id", "name", name="uq_horse_service_equestrian_name"),
    Index("ix_horse_service_equestrian_slug", "equestrian_id", "slug", unique=True),
)

horse_service_relations = Table(
    "horse_service_relations",
    metadata,
    uuid_pk(),
    timestamp_columns()[0],
    Column("horse_id", ForeignKey("horse.id", ondelete="CASCADE"), nullable=False),
    Column(
        "service_id", ForeignKey("horse_service.id", ondelete="CASCADE"), nullable=False
    ),
    Column("description_override", String(511), nullable=True),
    Column("price_override", Integer(), nullable=True),
    Column("price_formatter_override", String(7), nullable=True),
)
