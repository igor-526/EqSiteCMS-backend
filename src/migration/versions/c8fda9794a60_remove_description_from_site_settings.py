"""remove_description_from_site_settings

Revision ID: c8fda9794a60
Revises: 7d28fbc9a631
Create Date: 2026-09-22 08:29:54.875104

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8fda9794a60"
down_revision: Union[str, Sequence[str], None] = "7d28fbc9a631"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column("site_settings", "description")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "site_settings",
        sa.Column(
            "description",
            sa.String(length=511),
            autoincrement=False,
            nullable=True,
        ),
    )
