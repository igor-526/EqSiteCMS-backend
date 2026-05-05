from datetime import date
from typing import Any, Awaitable, Callable, Literal, Mapping, cast
from uuid import UUID

from pydantic import BaseModel, ValidationError, model_validator

from core.entities import (
    _HORSE_AVAILABLE_SORT_FIELDS,
    Breed,
    CoatColor,
    Horse,
    HorseKindEnum,
    HorseOwner,
    HorseServiceEntity,
    HorseSexEnum,
    PaginatedEntities,
    Photo,
)
from core.exceptions.base import ClientError
from core.protocols.repositories import (
    BreedRepositoryProtocol,
    CoatColorRepositoryProtocol,
    HorseOwnerRepositoryProtocol,
    HorseRepositoryProtocol,
)
from core.protocols.repositories.horse_repository import HorseChildrenRepositoryProtocol
from core.schemas import (
    BreedOutDto,
    CoatColorOutDto,
    HorseCreateInDto,
    HorseOutDto,
    HorseOwnerCreateInDto,
    HorseOwnerOutDto,
    HorsePedigree,
    HorseServiceOutDto,
    HorseSetPedigreeInDto,
    HorseUpdateInDto,
    HorseWithPedigreeOutDto,
    PhotoOutShortDto,
    UserOutDto,
)
from core.schemas.horses import SetPedigreeEntities


class HorseService:
    """Сервис для работы с лошадьми."""

    def __init__(
        self,
        horse_repository: HorseRepositoryProtocol,
        horse_children_repository: HorseChildrenRepositoryProtocol,
        breed_repository: BreedRepositoryProtocol,
        coat_color_repository: CoatColorRepositoryProtocol,
        horse_owner_repository: HorseOwnerRepositoryProtocol,
    ):
        self.horse_repository = horse_repository
        self.horse_children_repository = horse_children_repository
        self.breed_repository = breed_repository
        self.coat_color_repository = coat_color_repository
        self.horse_owner_repository = horse_owner_repository

    async def _check_admin_permission(
        self, *, user: UserOutDto | None, raise_exception: bool = False
    ) -> bool:
        """Проверить права администратора."""
        if user is None:
            if raise_exception:
                raise ClientError("Пользователь не авторизован")
            return False
        return True
        raise ClientError("Пользователь не имеет прав на это действие")

    def _get_horse_dto(
        self,
        *,
        horse: Horse,
        breed: Breed | None,
        coat_color: CoatColor | None,
        horse_owner: HorseOwner | None,
        photos: list[Photo],
        services: list[HorseServiceEntity],
    ) -> HorseOutDto:
        breed_dto = BreedOutDto(**breed.model_dump()) if breed is not None else None
        coat_color_dto = (
            CoatColorOutDto(**coat_color.model_dump())
            if coat_color is not None
            else None
        )
        horse_owner_dto = (
            HorseOwnerOutDto(**horse_owner.model_dump())
            if horse_owner is not None
            else None
        )
        photos_dto = [PhotoOutShortDto(**photo.model_dump()) for photo in photos]
        services_dto = [
            HorseServiceOutDto(**service.model_dump()) for service in services
        ]
        return HorseOutDto(
            id=horse.id,
            slug=horse.slug or "",
            name=horse.name,
            description=horse.description,
            breed=breed_dto,
            coat_color=coat_color_dto,
            kind=horse.kind,
            height=horse.height,
            sex=horse.sex,
            bdate=horse.bdate,
            ddate=horse.ddate,
            bdate_mode=horse.bdate_mode,
            ddate_mode=horse.ddate_mode,
            horse_owner=horse_owner_dto,
            photos=photos_dto,
            services=services_dto,
            this_stable=horse.this_stable,
        )

    async def _get_horse_by_id(
        self, *, horse_id: UUID, pedigree: int | None = None
    ) -> HorseOutDto | HorseWithPedigreeOutDto:
        """Получить лошадь по ID."""
        horse = await self.horse_repository.get_horse_full_info_by_id(
            horse_id=horse_id, pedigree=pedigree
        )
        if horse is None:
            raise ClientError("Лошадь не найдена")
        return horse

    async def _get_horse_by_slug(
        self, *, horse_slug: str, pedigree: int | None = None
    ) -> HorseOutDto | HorseWithPedigreeOutDto:
        """Получить лошадь по slug."""
        horse = await self.horse_repository.get_horse_full_info_by_slug(
            horse_slug=horse_slug, pedigree=pedigree
        )
        if horse is None:
            raise ClientError("Лошадь не найдена")
        return horse

    async def _get_breed_by_id(self, *, breed_id: UUID) -> Breed:
        """Получить породу по ID."""
        breed = await self.breed_repository.get_by_id(breed_id)
        if breed is None:
            raise ClientError("Порода не найдена")
        return breed

    async def _get_coat_color_by_id(self, *, coat_color_id: UUID) -> CoatColor:
        """Получить масть по ID."""
        coat_color = await self.coat_color_repository.get_by_id(coat_color_id)
        if coat_color is None:
            raise ClientError("Масть не найдена")
        return coat_color

    async def _get_horse_owner_by_id(self, *, horse_owner_id: UUID) -> HorseOwner:
        """Получить владельца по ID."""
        horse_owner = await self.horse_owner_repository.get_by_id(horse_owner_id)
        if horse_owner is None:
            raise ClientError("Владелец не найден")
        return horse_owner

    async def create_horse(
        self, *, create_data: HorseCreateInDto, user: UserOutDto | None = None
    ) -> HorseOutDto:
        """Создать новую лошадь."""
        await self._check_admin_permission(user=user, raise_exception=True)
        horse_breed: Breed | None = None
        horse_coat_color: CoatColor | None = None
        horse_owner: HorseOwner | None = None
        if create_data.breed_id is not None:
            horse_breed = await self._get_breed_by_id(breed_id=create_data.breed_id)
        if create_data.coat_color_id is not None:
            horse_coat_color = await self._get_coat_color_by_id(
                coat_color_id=create_data.coat_color_id
            )
        if create_data.horse_owner_id is not None:
            horse_owner = await self._get_horse_owner_by_id(
                horse_owner_id=create_data.horse_owner_id
            )
        try:
            horse = Horse(
                name=create_data.name,
                description=create_data.description,
                breed_id=create_data.breed_id,
                coat_color_id=create_data.coat_color_id,
                kind=create_data.kind,
                height=create_data.height,
                sex=create_data.sex,
                bdate=create_data.bdate,
                ddate=create_data.ddate,
                bdate_mode=create_data.bdate_mode,
                ddate_mode=create_data.ddate_mode,
                horse_owner_id=create_data.horse_owner_id,
                this_stable=create_data.this_stable,
            )
        except ValidationError as ex:
            raise ClientError(str(ex))
        new_horse = await self.horse_repository.create(horse)
        return self._get_horse_dto(
            horse=new_horse,
            breed=horse_breed,
            coat_color=horse_coat_color,
            horse_owner=horse_owner,
            photos=[],
            services=[],
        )

    async def update_horse(
        self, *, horse_id: UUID, data: HorseUpdateInDto, user: UserOutDto | None = None
    ) -> HorseOutDto:
        """Обновить лошадь."""
        await self._check_admin_permission(user=user, raise_exception=True)
        horse = await self.horse_repository.get_by_id(horse_id)
        if horse is None:
            raise ClientError("Лошадь не найдена")
        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            raise ClientError("Нет данных для обновления")
        update_data = {}
        if "breed_id" in update_data:
            await self._get_breed_by_id(breed_id=update_data["breed_id"])
            update_data["breed_id"] = data.breed_id
        if "coat_color_id" in update_data:
            await self._get_coat_color_by_id(coat_color_id=update_data["coat_color_id"])
            update_data["coat_color_id"] = data.coat_color_id
        if "horse_owner_id" in update_data:
            await self._get_horse_owner_by_id(
                horse_owner_id=update_data["horse_owner_id"]
            )
            update_data["horse_owner_id"] = data.horse_owner_id
        for key, value in update_data.items():
            setattr(horse, key, value)
        await self.horse_repository.update(horse)
        updated_horse = await self.horse_repository.get_horse_full_info_by_id(
            horse_id=horse.id
        )
        if updated_horse is None:
            raise ClientError("Лошадь не найдена")
        return HorseOutDto.model_validate(updated_horse)

    async def get_horse_by_slug_or_id(
        self, *, slug_or_id: str, pedigree: int | None = None, user: UserOutDto | None
    ) -> HorseOutDto | HorseWithPedigreeOutDto:
        """Получить лошадь по slug или ID."""
        mode: Literal["slug", "id"] = "slug"
        value: UUID | str = slug_or_id
        try:
            value = UUID(slug_or_id)
            mode = "id"
        except ValueError:
            mode = "slug"
            value = slug_or_id

        horse_dto: HorseOutDto | HorseWithPedigreeOutDto
        match mode:
            case "slug":
                horse_dto = await self._get_horse_by_slug(
                    horse_slug=cast(str, value), pedigree=pedigree
                )
            case "id":
                horse_dto = await self._get_horse_by_id(
                    horse_id=cast(UUID, value), pedigree=pedigree
                )
        return horse_dto

    async def get_available_pedigree(
        self,
        *,
        user: UserOutDto | None = None,
        horse_id: UUID,
        mode: Literal["sire", "dame", "children"],
        search: str | None = None,
        limit: int | None = 25,
        offset: int | None = 0,
    ) -> PaginatedEntities[HorseOutDto]:
        """Получить доступных производителей."""
        if limit is not None and limit > 50:
            limit = 50
        if limit is not None and limit < 1:
            limit = 1
        if offset is not None and offset < 0:
            offset = 0
        await self._check_admin_permission(user=user, raise_exception=True)
        target_horse = await self.horse_repository.get_by_id(horse_id)
        if target_horse is None:
            raise ClientError("Лошадь не найдена")
        _PEDIGREE_METHODS_REGISTRY: dict[
            Literal["sire", "dame", "children"],
            Callable[..., Awaitable[tuple[Mapping[UUID, HorseOutDto], int]]],
        ] = {
            "sire": self.horse_repository.get_available_sires,
            "dame": self.horse_repository.get_available_dames,
            "children": self.horse_repository.get_available_children,
        }
        horses, total = await _PEDIGREE_METHODS_REGISTRY[mode](
            target_horse=target_horse,
            search=search,
            limit=limit,
            offset=offset,
        )
        return PaginatedEntities(
            items=[HorseOutDto.model_validate(h) for h in horses.values()],
            total=total,
        )

    async def set_horse_pedigree(
        self,
        *,
        horse_id: UUID,
        pedigree_data: HorseSetPedigreeInDto,
        user: UserOutDto | None = None,
    ) -> None:
        """Установить родословное древо лошади."""

        await self._check_admin_permission(user=user, raise_exception=True)

        target: Horse | None = None
        sire: Horse | None = None
        dam: Horse | None = None
        foals: list[Horse] | None = None

        horses_ids_to_check: list[UUID] = [horse_id]
        if pedigree_data.sire_id is not None:
            horses_ids_to_check.append(pedigree_data.sire_id)
        if pedigree_data.dam_id is not None:
            horses_ids_to_check.append(pedigree_data.dam_id)
        if pedigree_data.foals is not None:
            horses_ids_to_check.extend(pedigree_data.foals)
        horses_mapping: Mapping[UUID, Horse] = await self.horse_repository.get_by_ids(
            horses_ids_to_check
        )
        if len(horses_mapping) != len(horses_ids_to_check):
            raise ClientError("Некоторые лошади не найдены")

        target = horses_mapping.get(horse_id)
        if pedigree_data.sire_id is not None:
            sire = horses_mapping.get(pedigree_data.sire_id)
        if pedigree_data.dam_id is not None:
            dam = horses_mapping.get(pedigree_data.dam_id)
        if pedigree_data.foals is not None:
            foals = [horses_mapping[foal_id] for foal_id in pedigree_data.foals]

        try:
            set_pedigree_entities = SetPedigreeEntities(
                target_horse=cast(Horse, target),
                sire=cast(Horse, sire),
                dam=cast(Horse, dam),
                foals=cast(list[Horse], foals),
            )
        except ValidationError as ex:
            raise ClientError(str(ex))

        await self.horse_children_repository.clear_pedigree(
            target_horse_id=set_pedigree_entities.target_horse.id,
            sire=set_pedigree_entities.sire is not None,
            dam=set_pedigree_entities.dam is not None,
            foals=set_pedigree_entities.foals is not None,
        )
        await self.horse_children_repository.set_pedigree(
            target_horse_id=set_pedigree_entities.target_horse.id,
            sire_id=(
                set_pedigree_entities.sire.id
                if set_pedigree_entities.sire is not None
                else None
            ),
            dam_id=(
                set_pedigree_entities.dam.id
                if set_pedigree_entities.dam is not None
                else None
            ),
            foals_ids=(
                [foal.id for foal in set_pedigree_entities.foals]
                if set_pedigree_entities.foals is not None
                else None
            ),
        )

    async def delete_horse(
        self, *, horse_id: UUID, user: UserOutDto | None = None
    ) -> None:
        """Удалить лошадь."""
        await self._check_admin_permission(user=user, raise_exception=True)

        horse = await self.horse_repository.get_by_id(horse_id)
        if horse is None:
            raise ClientError("Лошадь не найдена")
        await self.horse_repository.delete(horse_id)

    async def get_filtered_horses(
        self,
        *,
        user: UserOutDto | None = None,
        name: str | None = None,
        description: str | None = None,
        breed_ids: list[UUID] | None = None,
        coat_color_ids: list[UUID] | None = None,
        kind: list[HorseKindEnum] | None = None,
        height_gte: int | None = None,
        height_lte: int | None = None,
        sex: list[HorseSexEnum] | None = None,
        bdate_gte: date | None = None,
        bdate_lte: date | None = None,
        ddate_gte: date | None = None,
        ddate_lte: date | None = None,
        horse_owner_ids: list[UUID] | None = None,
        pedigree: int | None = None,
        this_stable: bool | None = None,
        exclude_ids: list[UUID] | None = None,
        include_ids: list[UUID] | None = None,
        limit: int | None = 25,
        offset: int | None = 0,
        sort: list[_HORSE_AVAILABLE_SORT_FIELDS] | None = None,
    ) -> PaginatedEntities[HorseOutDto | HorseWithPedigreeOutDto]:
        """Получить отфильтрованный список лошадей."""
        if limit is not None and limit > 100:
            limit = 100
        if limit is not None and limit < 1:
            limit = 1
        if offset is not None and offset < 0:
            offset = 0
        if pedigree is not None and pedigree > 3:
            pedigree = 3
        if pedigree is not None and pedigree < 0:
            pedigree = None
        horses, total = await self.horse_repository.get_horse_list_full_info(
            name=name,
            description=description,
            breed_ids=breed_ids,
            coat_color_ids=coat_color_ids,
            kind=kind,
            height_gte=height_gte,
            height_lte=height_lte,
            sex=sex,
            bdate_gte=bdate_gte,
            bdate_lte=bdate_lte,
            ddate_gte=ddate_gte,
            ddate_lte=ddate_lte,
            horse_owner_ids=horse_owner_ids,
            this_stable=this_stable,
            exclude_ids=exclude_ids,
            include_ids=include_ids,
            limit=limit,
            offset=offset,
            sort=sort,
            pedigree=pedigree,
        )
        return PaginatedEntities(
            items=list(horses.values()),
            total=total,
        )

    async def add_horse_service(self):
        """Добавить услугу к лошади."""
        ...

    async def remove_horse_service(self):
        """Удалить услугу из лошади."""
        ...

    async def update_horse_service(self):
        """Обновить услугу лошади."""
        ...
