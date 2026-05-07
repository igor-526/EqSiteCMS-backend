from sqlalchemy import Column, ForeignKey, Index, String, Table, Text, UniqueConstraint

from utils.basemodel import metadata, timestamp_columns, uuid_pk

coat_color = Table(
    "coat_color",
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
    Column("short_name", String(63), nullable=True),
    Column("slug", String(63), nullable=False, index=True),
    Column("description", String(511), nullable=True),
    Column("page_data", Text(), nullable=False, default="<div></div>"),
    UniqueConstraint("equestrian_id", "name", name="uq_coat_color_equestrian_name"),
    Index("ix_coat_color_equestrian_slug", "equestrian_id", "slug", unique=True),
)
