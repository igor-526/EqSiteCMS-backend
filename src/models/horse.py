from sqlalchemy import Boolean, Column, Date, ForeignKey, Integer, String, Table, Text

from utils.basemodel import metadata, timestamp_columns, uuid_pk

horse = Table(
    "horse",
    metadata,
    uuid_pk(),
    *timestamp_columns(),
    Column("name", String(63), nullable=False, index=True),
    Column("slug", String(63), nullable=False, index=True),
    Column("description", String(511), nullable=True),
    Column("breed_id", ForeignKey("breeds.id", ondelete="CASCADE"), nullable=True),
    Column(
        "coat_color_id", ForeignKey("coat_color.id", ondelete="CASCADE"), nullable=True
    ),
    Column("kind", String(7), nullable=False),
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
