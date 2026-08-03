from uuid import UUID

from core.entities.base import PaginatedEntities
from core.entities.equestrian import EquestrianContext
from core.entities.horse_service import HorseServiceRelations
from core.exceptions.auth import ForbiddenError
from core.exceptions.base import ClientError, ConflictError, NotFoundError
from core.protocols.repositories.horse_repository import HorseRepositoryProtocol
from core.protocols.repositories.horse_service_relations_repository import (
    HorseServiceRelationsRepositoryProtocol,
)
from core.protocols.repositories.horse_service_repository import (
    HorseServiceRepositoryProtocol,
)
from core.schemas.horse_service_relations import (
    HorseServiceAvailableOutDto,
    HorseServiceRelationCreateDto,
    HorseServiceRelationOutDto,
    HorseServiceRelationUpdateDto,
)
from core.schemas.users import UserOutDto


class HorseServiceRelationsService:
    _ADMIN_SCOPE_NAMES: frozenset[str] = frozenset({"SUPERUSER", "ADMIN", "DEVELOPER"})

    def __init__(
        self,
        relations_repository: HorseServiceRelationsRepositoryProtocol,
        horse_repository: HorseRepositoryProtocol,
        horse_service_repository: HorseServiceRepositoryProtocol,
    ) -> None:
        self.relations_repository = relations_repository
        self.horse_repository = horse_repository
        self.horse_service_repository = horse_service_repository

    def _require_write_scope(self, *, user: UserOutDto) -> None:
        if not any(
            scope.scope_name in self._ADMIN_SCOPE_NAMES for scope in user.scopes
        ):
            raise ForbiddenError("Недостаточно прав для выполнения операции")

    async def _validate_horse_exists(
        self, horse_id: UUID, *, equestrian_id: UUID
    ) -> None:
        horse = await self.horse_repository.get_by_id(
            horse_id, equestrian_id=equestrian_id
        )
        if horse is None:
            raise NotFoundError("Лошадь не найдена")

    async def _validate_service_exists(
        self, service_id: UUID, *, equestrian_id: UUID
    ) -> None:
        service = await self.horse_service_repository.get_by_id(
            service_id, equestrian_id=equestrian_id
        )
        if service is None:
            raise NotFoundError("Услуга не найдена")

    def _build_out_dto(
        self,
        relation: HorseServiceRelations,
        service_name: str,
        service_slug: str,
        service_description: str | None,
        service_price: int,
        service_price_formatter: str,
    ) -> HorseServiceRelationOutDto:
        return HorseServiceRelationOutDto(
            id=relation.id,
            created_at=relation.created_at,
            service_id=relation.service_id,
            name=service_name,
            slug=service_slug,
            description=(
                relation.description_override
                if relation.description_override is not None
                else service_description
            ),
            price=(
                relation.price_override
                if relation.price_override is not None
                else service_price
            ),
            price_formatter=(
                relation.price_formatter_override
                if relation.price_formatter_override is not None
                else service_price_formatter
            ),
        )

    async def _get_service_and_build_dto(
        self, relation: HorseServiceRelations, *, equestrian_id: UUID
    ) -> HorseServiceRelationOutDto:
        service = await self.horse_service_repository.get_by_id(
            relation.service_id, equestrian_id=equestrian_id
        )
        if service is None:
            raise ClientError("Услуга не найдена")
        return self._build_out_dto(
            relation,
            service.name,
            service.slug or "",
            service.description,
            service.price,
            str(service.price_formatter),
        )

    async def create(
        self,
        horse_id: UUID,
        data: HorseServiceRelationCreateDto,
        *,
        equestrian_context: EquestrianContext,
        user: UserOutDto,
    ) -> HorseServiceRelationOutDto:
        self._require_write_scope(user=user)
        await self._validate_horse_exists(horse_id, equestrian_id=equestrian_context.id)
        await self._validate_service_exists(
            data.service_id, equestrian_id=equestrian_context.id
        )

        existing = await self.relations_repository.get_by_horse_and_service(
            horse_id=horse_id, service_id=data.service_id
        )
        if existing is not None:
            raise ConflictError("Услуга уже привязана к этой лошади")

        relation = HorseServiceRelations(
            horse_id=horse_id,
            service_id=data.service_id,
            description_override=data.description_override,
            price_override=data.price_override,
            price_formatter_override=data.price_formatter_override,
        )
        created = await self.relations_repository.create(relation)
        return await self._get_service_and_build_dto(
            created, equestrian_id=equestrian_context.id
        )

    async def update(
        self,
        horse_id: UUID,
        relation_id: UUID,
        data: HorseServiceRelationUpdateDto,
        *,
        equestrian_context: EquestrianContext,
        user: UserOutDto,
    ) -> HorseServiceRelationOutDto:
        self._require_write_scope(user=user)
        await self._validate_horse_exists(horse_id, equestrian_id=equestrian_context.id)

        relation = await self.relations_repository.get_by_id_and_horse(
            relation_id=relation_id, horse_id=horse_id
        )
        if relation is None:
            raise NotFoundError("Связь не найдена")

        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            raise ClientError("Нет данных для обновления")

        for key, value in update_data.items():
            setattr(relation, key, value)

        updated = await self.relations_repository.update(relation)
        return await self._get_service_and_build_dto(
            updated, equestrian_id=equestrian_context.id
        )

    async def delete(
        self,
        horse_id: UUID,
        relation_id: UUID,
        *,
        equestrian_context: EquestrianContext,
        user: UserOutDto,
    ) -> None:
        self._require_write_scope(user=user)
        await self._validate_horse_exists(horse_id, equestrian_id=equestrian_context.id)

        relation = await self.relations_repository.get_by_id_and_horse(
            relation_id=relation_id, horse_id=horse_id
        )
        if relation is None:
            raise NotFoundError("Связь не найдена")

        await self.relations_repository.delete(relation.id)

    async def get_list_by_horse(
        self,
        horse_id: UUID,
        *,
        equestrian_context: EquestrianContext,
        limit: int | None = None,
        offset: int | None = None,
    ) -> PaginatedEntities[HorseServiceRelationOutDto]:
        await self._validate_horse_exists(horse_id, equestrian_id=equestrian_context.id)

        relations, total = await self.relations_repository.get_list_by_horse(
            horse_id=horse_id, limit=limit, offset=offset
        )
        result = []
        for relation in relations:
            dto = await self._get_service_and_build_dto(
                relation, equestrian_id=equestrian_context.id
            )
            result.append(dto)
        return PaginatedEntities(items=result, total=total)

    async def get_available_services(
        self,
        horse_id: UUID,
        *,
        equestrian_context: EquestrianContext,
        user: UserOutDto,
        search: str | None = None,
    ) -> list[HorseServiceAvailableOutDto]:
        self._require_write_scope(user=user)
        await self._validate_horse_exists(horse_id, equestrian_id=equestrian_context.id)

        services = await self.relations_repository.get_available_services(
            horse_id=horse_id, equestrian_id=equestrian_context.id, search=search
        )
        return [
            HorseServiceAvailableOutDto.model_validate(service) for service in services
        ]
