from sqlalchemy import Column, String, Table, text
from sqlalchemy.dialects.postgresql import JSONB

from utils.basemodel import metadata, timestamp_columns, uuid_pk

horse_owner = Table(
    "horse_owner",
    metadata,
    uuid_pk(),
    *timestamp_columns(),
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
)
