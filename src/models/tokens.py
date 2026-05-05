from sqlalchemy import Column, ForeignKey, String, Table

from utils.basemodel import metadata, timestamp_columns, uuid_pk

tokens = Table(
    "tokens",
    metadata,
    uuid_pk(),
    *timestamp_columns(),
    Column("value", String(1023), nullable=False),
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
)
