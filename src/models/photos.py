from sqlalchemy import Column, ForeignKey, Index, String, Table

from utils.basemodel import metadata, timestamp_columns, uuid_pk

photos = Table(
    "photos",
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
    Column("path", String(511), nullable=False),
    Index("ix_photos_equestrian_name", "equestrian_id", "name"),
)
