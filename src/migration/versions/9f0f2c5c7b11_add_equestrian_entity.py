"""Add equestrian root tenant and tenant-scoped columns.

Creates the default local tenant with service_key='default-equestrian' and
backfills all existing tenant-scoped rows to it. Downgrade removes tenant
columns and the equestrians table; it is destructive for multi-tenant data.

Revision ID: 9f0f2c5c7b11
Revises: 47d6367ed482
Create Date: 2026-05-07 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "9f0f2c5c7b11"
down_revision: Union[str, Sequence[str], None] = "47d6367ed482"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_SERVICE_KEY = "default-equestrian"
TENANT_TABLES = (
    "users",
    "breeds",
    "coat_color",
    "horse_owner",
    "horse_service",
    "horse",
    "photos",
    "prices",
    "price_groups",
    "site_settings",
)
TENANT_SCOPED_SLUG_TABLES = (
    "breeds",
    "coat_color",
    "horse_service",
    "horse",
    "prices",
)


def _deduplicate_tenant_scoped_slugs(table_name: str) -> None:
    op.execute(
        sa.text(
            f"""
            WITH ranked AS (
                SELECT
                    id,
                    row_number() OVER (
                        PARTITION BY equestrian_id, slug
                        ORDER BY created_at NULLS LAST, id
                    ) AS rn
                FROM {table_name}
            )
            UPDATE {table_name} AS target
            SET slug = CONCAT('legacy-', REPLACE(target.id::text, '-', ''))
            FROM ranked
            WHERE target.id = ranked.id
              AND ranked.rn > 1
            """
        )
    )


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.create_table(
        "equestrians",
        sa.Column(
            "id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name", sa.String(length=127), nullable=False),
        sa.Column("service_key", sa.String(length=127), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("service_key", name="uq_equestrians_service_key"),
    )
    op.create_index(
        "ix_equestrians_service_key", "equestrians", ["service_key"], unique=True
    )

    op.execute(
        sa.text(
            """
            INSERT INTO equestrians (name, service_key)
            SELECT 'Default Equestrian', :service_key
            WHERE NOT EXISTS (
                SELECT 1 FROM equestrians WHERE service_key = :service_key
            )
            """
        ).bindparams(service_key=DEFAULT_SERVICE_KEY)
    )

    for table_name in TENANT_TABLES:
        op.add_column(table_name, sa.Column("equestrian_id", sa.UUID(), nullable=True))
        op.execute(
            sa.text(
                f"""
                UPDATE {table_name}
                SET equestrian_id = (
                    SELECT id FROM equestrians WHERE service_key = :service_key
                )
                WHERE equestrian_id IS NULL
                """
            ).bindparams(service_key=DEFAULT_SERVICE_KEY)
        )
        op.alter_column(
            table_name, "equestrian_id", existing_type=sa.UUID(), nullable=False
        )
        op.create_foreign_key(
            f"fk_{table_name}_equestrian_id_equestrians",
            table_name,
            "equestrians",
            ["equestrian_id"],
            ["id"],
            ondelete="RESTRICT" if table_name == "users" else "CASCADE",
        )
        op.create_index(
            f"ix_{table_name}_equestrian_id",
            table_name,
            ["equestrian_id"],
            unique=False,
        )

    op.drop_index("ix_breeds_name", table_name="breeds")
    op.drop_index("ix_coat_color_name", table_name="coat_color")
    op.drop_index("ix_horse_service_name", table_name="horse_service")
    op.drop_index("ix_site_settings_key", table_name="site_settings")
    op.drop_index("ix_site_settings_name", table_name="site_settings")

    op.create_index("ix_breeds_name", "breeds", ["name"], unique=False)
    op.create_index("ix_coat_color_name", "coat_color", ["name"], unique=False)
    op.create_index("ix_horse_service_name", "horse_service", ["name"], unique=False)
    op.create_index("ix_site_settings_key", "site_settings", ["key"], unique=False)
    op.create_index("ix_site_settings_name", "site_settings", ["name"], unique=False)

    for table_name in TENANT_SCOPED_SLUG_TABLES:
        _deduplicate_tenant_scoped_slugs(table_name)

    op.create_unique_constraint(
        "uq_breeds_equestrian_name", "breeds", ["equestrian_id", "name"]
    )
    op.create_index(
        "ix_breeds_equestrian_slug", "breeds", ["equestrian_id", "slug"], unique=True
    )
    op.create_unique_constraint(
        "uq_coat_color_equestrian_name", "coat_color", ["equestrian_id", "name"]
    )
    op.create_index(
        "ix_coat_color_equestrian_slug",
        "coat_color",
        ["equestrian_id", "slug"],
        unique=True,
    )
    op.create_unique_constraint(
        "uq_horse_service_equestrian_name", "horse_service", ["equestrian_id", "name"]
    )
    op.create_index(
        "ix_horse_service_equestrian_slug",
        "horse_service",
        ["equestrian_id", "slug"],
        unique=True,
    )
    op.create_index(
        "ix_horse_owner_equestrian_name", "horse_owner", ["equestrian_id", "name"]
    )
    op.create_index(
        "ix_horse_owner_equestrian_type", "horse_owner", ["equestrian_id", "type"]
    )
    op.create_index(
        "ix_horse_equestrian_slug", "horse", ["equestrian_id", "slug"], unique=True
    )
    op.create_index("ix_horse_equestrian_name", "horse", ["equestrian_id", "name"])
    op.create_index("ix_horse_equestrian_kind", "horse", ["equestrian_id", "kind"])
    op.create_index("ix_horse_equestrian_sex", "horse", ["equestrian_id", "sex"])
    op.create_index("ix_photos_equestrian_name", "photos", ["equestrian_id", "name"])
    op.create_index(
        "ix_prices_equestrian_slug", "prices", ["equestrian_id", "slug"], unique=True
    )
    op.create_index("ix_prices_equestrian_name", "prices", ["equestrian_id", "name"])
    op.create_index(
        "ix_price_groups_equestrian_name", "price_groups", ["equestrian_id", "name"]
    )
    op.create_unique_constraint(
        "uq_site_settings_equestrian_key", "site_settings", ["equestrian_id", "key"]
    )
    op.create_unique_constraint(
        "uq_site_settings_equestrian_name", "site_settings", ["equestrian_id", "name"]
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_site_settings_equestrian_name", "site_settings", type_="unique"
    )
    op.drop_constraint(
        "uq_site_settings_equestrian_key", "site_settings", type_="unique"
    )
    op.drop_index("ix_price_groups_equestrian_name", table_name="price_groups")
    op.drop_index("ix_prices_equestrian_name", table_name="prices")
    op.drop_index("ix_prices_equestrian_slug", table_name="prices")
    op.drop_index("ix_photos_equestrian_name", table_name="photos")
    op.drop_index("ix_horse_equestrian_sex", table_name="horse")
    op.drop_index("ix_horse_equestrian_kind", table_name="horse")
    op.drop_index("ix_horse_equestrian_name", table_name="horse")
    op.drop_index("ix_horse_equestrian_slug", table_name="horse")
    op.drop_index("ix_horse_owner_equestrian_type", table_name="horse_owner")
    op.drop_index("ix_horse_owner_equestrian_name", table_name="horse_owner")
    op.drop_index("ix_horse_service_equestrian_slug", table_name="horse_service")
    op.drop_constraint(
        "uq_horse_service_equestrian_name", "horse_service", type_="unique"
    )
    op.drop_index("ix_coat_color_equestrian_slug", table_name="coat_color")
    op.drop_constraint("uq_coat_color_equestrian_name", "coat_color", type_="unique")
    op.drop_index("ix_breeds_equestrian_slug", table_name="breeds")
    op.drop_constraint("uq_breeds_equestrian_name", "breeds", type_="unique")

    op.drop_index("ix_site_settings_name", table_name="site_settings")
    op.drop_index("ix_site_settings_key", table_name="site_settings")
    op.drop_index("ix_horse_service_name", table_name="horse_service")
    op.drop_index("ix_coat_color_name", table_name="coat_color")
    op.drop_index("ix_breeds_name", table_name="breeds")
    op.create_index("ix_site_settings_name", "site_settings", ["name"], unique=True)
    op.create_index("ix_site_settings_key", "site_settings", ["key"], unique=True)
    op.create_index("ix_horse_service_name", "horse_service", ["name"], unique=True)
    op.create_index("ix_coat_color_name", "coat_color", ["name"], unique=True)
    op.create_index("ix_breeds_name", "breeds", ["name"], unique=True)

    for table_name in reversed(TENANT_TABLES):
        op.drop_index(f"ix_{table_name}_equestrian_id", table_name=table_name)
        op.drop_constraint(
            f"fk_{table_name}_equestrian_id_equestrians", table_name, type_="foreignkey"
        )
        op.drop_column(table_name, "equestrian_id")

    op.drop_index("ix_equestrians_service_key", table_name="equestrians")
    op.drop_table("equestrians")
