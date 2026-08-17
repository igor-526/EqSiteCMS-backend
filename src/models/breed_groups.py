from sqlalchemy import Column, ForeignKey, Index, String, Table, Text, UniqueConstraint

from utils.basemodel import metadata, timestamp_columns, uuid_pk

breed_groups = Table(
    "breed_groups",
    metadata,
    uuid_pk(),
    *timestamp_columns(),
    Column(
        "equestrian_id",
        ForeignKey("equestrians.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    ),
    Column("name", String(63), nullable=False),
    Column("slug", String(63), nullable=False),
    Column("page_data", Text(), nullable=False, server_default="<div></div>"),
    UniqueConstraint("equestrian_id", "name", name="uq_breed_groups_equestrian_name"),
    Index("ix_breed_groups_equestrian_slug", "equestrian_id", "slug", unique=True),
)
