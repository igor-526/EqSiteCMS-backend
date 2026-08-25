"""Add callback request journal and status registry."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c055bacc0001"
down_revision: Union[str, Sequence[str], None] = "f3a1c7d9e245"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "callback_request_statuses",
        sa.Column("id", sa.SmallInteger(), primary_key=True),
        sa.Column("name", sa.String(63), nullable=False, unique=True),
        sa.Column("color", sa.String(7), nullable=False),
        sa.CheckConstraint(
            "color ~ '^#[0-9A-Fa-f]{6}$'", name="ck_callback_status_color_hex"
        ),
    )
    op.create_table(
        "callback_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "equestrian_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("equestrians.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(127), nullable=True),
        sa.Column("phone", sa.String(63), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.SmallInteger(),
            sa.ForeignKey("callback_request_statuses.id", ondelete="RESTRICT"),
            server_default=sa.text("1"),
            nullable=False,
        ),
        sa.Column(
            "is_spam", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "notifications_delivered",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_callback_requests_tenant_status_created",
        "callback_requests",
        ["equestrian_id", "status", "created_at", "id"],
    )
    op.create_index(
        "ix_callback_requests_tenant_spam",
        "callback_requests",
        ["equestrian_id", "is_spam"],
    )


def downgrade() -> None:
    op.drop_index("ix_callback_requests_tenant_spam", table_name="callback_requests")
    op.drop_index(
        "ix_callback_requests_tenant_status_created", table_name="callback_requests"
    )
    op.drop_table("callback_requests")
    op.drop_table("callback_request_statuses")
