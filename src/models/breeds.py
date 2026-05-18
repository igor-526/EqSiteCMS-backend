from sqlalchemy import Column, ForeignKey, Index, String, Table, Text, UniqueConstraint

from utils.basemodel import metadata, timestamp_columns, uuid_pk

breeds = Table(
    "breeds",
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
    Column("short_name", String(63), nullable=False),
    Column("slug", String(63), nullable=False, index=True),
    Column("description", String(511), nullable=True),
    Column("page_data", Text(), nullable=False, default="<div></div>"),
    Column("kind", String(7), nullable=False, server_default="horse"),
    UniqueConstraint("equestrian_id", "name", name="uq_breeds_equestrian_name"),
    Index("ix_breeds_equestrian_slug", "equestrian_id", "slug", unique=True),
    Index("ix_breeds_equestrian_kind", "equestrian_id", "kind"),
)
