from sqlalchemy import (
    Boolean,
    Column,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
)

from utils.basemodel import metadata, timestamp_columns, uuid_pk

horse = Table(
    "horse",
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
    Column("pedigree_name", String(63), nullable=True),
    Column("slug", String(63), nullable=False, index=True),
    Column("description", String(511), nullable=True),
    Column("breed_id", ForeignKey("breeds.id", ondelete="CASCADE"), nullable=True),
    Column(
        "coat_color_id", ForeignKey("coat_color.id", ondelete="CASCADE"), nullable=True
    ),
    Column("height", Integer(), nullable=True),
    Column("sex", String(7), nullable=False),
    Column("bdate", Date(), nullable=True),
    Column("ddate", Date(), nullable=True),
    Column("bdate_mode", String(7), nullable=False, default=0),
    Column("ddate_mode", String(7), nullable=False, default=0),
    Column(
        "horse_owner_id",
        ForeignKey("horse_owner.id", ondelete="CASCADE"),
        nullable=True,
    ),
    Column(
        "this_stable", Boolean(), nullable=False, default=True, server_default="true"
    ),
    Index("ix_horse_equestrian_slug", "equestrian_id", "slug", unique=True),
    Index("ix_horse_equestrian_name", "equestrian_id", "name"),
    Index("ix_horse_equestrian_sex", "equestrian_id", "sex"),
)

horse_children = Table(
    "horse_children",
    metadata,
    uuid_pk(),
    *timestamp_columns(),
    Column("horse_id", ForeignKey("horse.id", ondelete="CASCADE"), nullable=False),
    Column("child_id", ForeignKey("horse.id", ondelete="CASCADE"), nullable=False),
)

horse_photos = Table(
    "horse_photos",
    metadata,
    uuid_pk(),
    *timestamp_columns(),
    Column("horse_id", ForeignKey("horse.id", ondelete="CASCADE"), nullable=False),
    Column("photo_id", ForeignKey("photos.id", ondelete="CASCADE"), nullable=False),
    Column("is_main", Boolean(), nullable=False, default=False),
)
