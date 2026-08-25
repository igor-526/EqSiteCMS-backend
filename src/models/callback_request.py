from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Table,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from utils.basemodel import metadata, timestamp_columns, uuid_pk

callback_request_statuses = Table(
    "callback_request_statuses",
    metadata,
    Column("id", SmallInteger, primary_key=True),
    Column("name", String(63), nullable=False, unique=True),
    Column("color", String(7), nullable=False),
    CheckConstraint("color ~ '^#[0-9A-Fa-f]{6}$'", name="ck_callback_status_color_hex"),
)

callback_requests = Table(
    "callback_requests",
    metadata,
    uuid_pk(),
    *timestamp_columns(),
    Column(
        "equestrian_id",
        UUID(as_uuid=True),
        ForeignKey("equestrians.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("name", String(127), nullable=True),
    Column("phone", String(63), nullable=False),
    Column("comment", Text, nullable=True),
    Column(
        "status",
        SmallInteger,
        ForeignKey("callback_request_statuses.id", ondelete="RESTRICT"),
        nullable=False,
        server_default=text("1"),
    ),
    Column("is_spam", Boolean, nullable=False, server_default=text("false")),
    Column(
        "notifications_delivered", Boolean, nullable=False, server_default=text("false")
    ),
    Index(
        "ix_callback_requests_tenant_status_created",
        "equestrian_id",
        "status",
        "created_at",
        "id",
    ),
    Index("ix_callback_requests_tenant_spam", "equestrian_id", "is_spam"),
)
