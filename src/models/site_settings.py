from sqlalchemy import Column, String, Table, Text

from utils.basemodel import metadata, timestamp_columns, uuid_pk

site_settings = Table(
    "site_settings",
    metadata,
    uuid_pk(),
    *timestamp_columns(),
    Column("key", String(63), nullable=False, unique=True, index=True),
    Column("value", Text(), nullable=False),
    Column("name", String(63), nullable=False, unique=True, index=True),
    Column("description", String(511), nullable=True),
    Column("type", String(10), nullable=False),
)
