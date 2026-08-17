from datetime import UTC, datetime
from uuid import UUID

from core.entities.equestrian import EquestrianContext
from core.entities.user import UserScope
from core.schemas.users import UserOutDto

TEST_EQUESTRIAN_CONTEXT = EquestrianContext(
    id=UUID("11111111-1111-4111-8111-111111111111"),
    source="unit-test",
)

TEST_ADMIN_USER = UserOutDto(
    id=UUID("99999999-9999-4999-8999-999999999999"),
    equestrian_id=TEST_EQUESTRIAN_CONTEXT.id,
    username="unit-admin",
    created_at=datetime.now(UTC),
    scopes=[UserScope(scope_name="ADMIN", scope_description="Unit admin")],
)
