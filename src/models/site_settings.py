from sqlalchemy import Column, ForeignKey, String, Table, Text, UniqueConstraint

from utils.basemodel import metadata, timestamp_columns, uuid_pk

site_settings = Table(
    "site_settings",
    metadata,
    uuid_pk(),
    *timestamp_columns(),
    Column(
        "equestrian_id",
        ForeignKey("equestrians.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("key", String(63), nullable=False, index=True),
    Column("value", Text(), nullable=False),
    Column("name", String(63), nullable=False, index=True),
    Column("description", String(511), nullable=True),
    Column("type", String(10), nullable=False),
    UniqueConstraint("equestrian_id", "key", name="uq_site_settings_equestrian_key"),
    UniqueConstraint("equestrian_id", "name", name="uq_site_settings_equestrian_name"),
)
