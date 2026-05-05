from sqlalchemy import Column, String, Table, Text

from utils.basemodel import metadata, timestamp_columns, uuid_pk

coat_color = Table(
    "coat_color",
    metadata,
    uuid_pk(),
    *timestamp_columns(),
    Column("name", String(63), nullable=False, unique=True, index=True),
    Column("short_name", String(63), nullable=True),
    Column("slug", String(63), nullable=False, index=True),
    Column("description", String(511), nullable=True),
    Column("page_data", Text(), nullable=False, default="<div></div>"),
)
