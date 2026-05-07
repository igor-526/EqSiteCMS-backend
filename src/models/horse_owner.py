from sqlalchemy import Column, ForeignKey, Index, String, Table, text
from sqlalchemy.dialects.postgresql import JSONB

from utils.basemodel import metadata, timestamp_columns, uuid_pk

horse_owner = Table(
    "horse_owner",
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
    Column("type", String(7), nullable=False),
    Column("address", String(511), nullable=True),
    Column(
        "phone_numbers",
        JSONB,
        nullable=False,
        server_default=text("'[]'::jsonb"),
    ),
    Index("ix_horse_owner_equestrian_name", "equestrian_id", "name"),
    Index("ix_horse_owner_equestrian_type", "equestrian_id", "type"),
)
