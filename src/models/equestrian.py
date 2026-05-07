from sqlalchemy import Column, String, Table

from utils.basemodel import metadata, timestamp_columns, uuid_pk

equestrians = Table(
    "equestrians",
    metadata,
    uuid_pk(),
    *timestamp_columns(),
    Column("name", String(127), nullable=False),
    Column("service_key", String(127), nullable=False, unique=True, index=True),
)
