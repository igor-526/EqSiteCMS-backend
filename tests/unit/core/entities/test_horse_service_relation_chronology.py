from datetime import datetime, timezone
from uuid import UUID

from core.entities.horse_service import HorseServiceRelations
from core.entities.price import PriceFormatter
from core.schemas.horse_service_relations import HorseServiceRelationOutDto


def test_ut05_relation_entity_and_schema_serialize_aware_created_at() -> None:
    created_at = datetime(2026, 8, 3, 12, 30, tzinfo=timezone.utc)
    relation = HorseServiceRelations(
        horse_id=UUID("11111111-1111-4111-8111-111111111111"),
        service_id=UUID("22222222-2222-4222-8222-222222222222"),
        created_at=created_at,
    )
    dto = HorseServiceRelationOutDto(
        id=relation.id,
        service_id=relation.service_id,
        name="Подковка",
        slug="podkovka",
        description=None,
        price=1000,
        price_formatter=PriceFormatter.equal,
        created_at=relation.created_at,
    )

    assert relation.created_at.tzinfo is timezone.utc
    assert dto.model_dump()["created_at"] == "2026-08-03T12:30:00+00:00"
