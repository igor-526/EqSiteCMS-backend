from datetime import date
from typing import Awaitable, Callable, Literal, Mapping, cast
from uuid import UUID

from pydantic import ValidationError

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
from core.entities.equestrian import EquestrianContext
from core.exceptions.auth import ForbiddenError
from core.exceptions.base import ClientError
from core.protocols.repositories import (
    BreedRepositoryProtocol,
    CoatColorRepositoryProtocol,
    HorseOwnerRepositoryProtocol,
    HorseRepositoryProtocol,
)
from core.protocols.repositories.horse_repository import HorseChildrenRepositoryProtocol
from core.protocols.repositories.photo_repository import PhotoRepositoryProtocol
from core.schemas import (
    BreedOutDto,
    CoatColorOutDto,
    HorseCreateInDto,
    HorseOutDto,
    HorseOwnerOutDto,
    HorsePhotosUpdateInDto,
    HorseServiceOutDto,
    HorseSetPedigreeInDto,
    HorseUpdateInDto,
    HorseWithPedigreeOutDto,
    PhotoOutShortDto,
    UserOutDto,
)

_PedigreeMode = Literal["sire", "dam", "children"]


class HorseService:
    """Сервис для работы с лошадьми."""

    _ADMIN_SCOPE_NAMES: frozenset[str] = frozenset({"SUPERUSER", "ADMIN", "DEVELOPER"})

    def __init__(
        self,
        horse_repository: HorseRepositoryProtocol,
        horse_children_repository: HorseChildrenRepositoryProtocol,
        breed_repository: BreedRepositoryProtocol,
        coat_color_repository: CoatColorRepositoryProtocol,
        horse_owner_repository: HorseOwnerRepositoryProtocol,
        photo_repository: PhotoRepositoryProtocol | None = None,
    ):
        self.horse_repository = horse_repository
        self.horse_children_repository = horse_children_repository
        self.breed_repository = breed_repository
        self.coat_color_repository = coat_color_repository
        self.horse_owner_repository = horse_owner_repository
        self.photo_repository = photo_repository

    async def _check_admin_permission(
        self, *, user: UserOutDto | None, raise_exception: bool = False
    ) -> bool:
        """Проверить права администратора."""
        if user is None:
            if raise_exception:
                raise ClientError("Пользователь не авторизован")
            return False
        has_admin_scope = any(
            scope.scope_name in self._ADMIN_SCOPE_NAMES for scope in user.scopes
        )
        if not has_admin_scope:
            if raise_exception:
                raise ForbiddenError("Недостаточно прав для выполнения операции")
            return False
        return True

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
            code=horse.code,
            description=horse.description,
            breed=breed_dto,
            coat_color=coat_color_dto,
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
        self,
        *,
        horse_id: UUID,
        equestrian_context: EquestrianContext,
        pedigree: int | None = None,
    ) -> HorseOutDto | HorseWithPedigreeOutDto:
        """Получить лошадь по ID."""
        horse = await self.horse_repository.get_horse_full_info_by_id(
            horse_id=horse_id,
            equestrian_id=equestrian_context.id,
            pedigree=pedigree,
        )
        if horse is None:
            raise ClientError("Лошадь не найдена")
        return horse

    async def _get_horse_by_slug(
        self,
        *,
        horse_slug: str,
        equestrian_context: EquestrianContext,
        pedigree: int | None = None,
    ) -> HorseOutDto | HorseWithPedigreeOutDto:
        """Получить лошадь по slug."""
        horse = await self.horse_repository.get_horse_full_info_by_slug(
            horse_slug=horse_slug,
            equestrian_id=equestrian_context.id,
            pedigree=pedigree,
        )
        if horse is None:
            raise ClientError("Лошадь не найдена")
        return horse

    async def _get_breed_by_id(
        self, *, breed_id: UUID, equestrian_context: EquestrianContext
    ) -> Breed:
        """Получить породу по ID."""
        breed = await self.breed_repository.get_by_id(
            breed_id, equestrian_id=equestrian_context.id
        )
        if breed is None:
            raise ClientError("Порода не найдена")
        return breed

    async def _get_breed_kind_for_horse(
        self, *, horse: Horse, equestrian_context: EquestrianContext
    ) -> HorseKindEnum | None:
        if horse.breed_id is None:
            return None
        breed = await self._get_breed_by_id(
            breed_id=horse.breed_id, equestrian_context=equestrian_context
        )
        return breed.kind

    async def _get_breed_kinds_for_horses(
        self, *, horses: Mapping[UUID, Horse], equestrian_context: EquestrianContext
    ) -> dict[UUID, HorseKindEnum | None]:
        kinds: dict[UUID, HorseKindEnum | None] = {}
        breed_cache: dict[UUID, HorseKindEnum] = {}
        for horse_item in horses.values():
            if horse_item.breed_id is None:
                kinds[horse_item.id] = None
                continue
            if horse_item.breed_id not in breed_cache:
                breed = await self._get_breed_by_id(
                    breed_id=horse_item.breed_id,
                    equestrian_context=equestrian_context,
                )
                breed_cache[horse_item.breed_id] = breed.kind
            kinds[horse_item.id] = breed_cache[horse_item.breed_id]
        return kinds

    async def _get_coat_color_by_id(
        self, *, coat_color_id: UUID, equestrian_context: EquestrianContext
    ) -> CoatColor:
        """Получить масть по ID."""
        coat_color = await self.coat_color_repository.get_by_id(
            coat_color_id, equestrian_id=equestrian_context.id
        )
        if coat_color is None:
            raise ClientError("Масть не найдена")
        return coat_color

    async def _get_horse_owner_by_id(
        self, *, horse_owner_id: UUID, equestrian_context: EquestrianContext
    ) -> HorseOwner:
        """Получить владельца по ID."""
        horse_owner = await self.horse_owner_repository.get_by_id(
            horse_owner_id, equestrian_id=equestrian_context.id
        )
        if horse_owner is None:
            raise ClientError("Владелец не найден")
        return horse_owner

    async def _get_current_pedigree_ids(
        self, *, horse_id: UUID, equestrian_context: EquestrianContext
    ) -> tuple[UUID | None, UUID | None, list[UUID]]:
        horse_with_pedigree = await self.horse_repository.get_horse_full_info_by_id(
            horse_id=horse_id,
            equestrian_id=equestrian_context.id,
            pedigree=1,
        )
        if horse_with_pedigree is None:
            raise ClientError("Лошадь не найдена")

        pedigree = getattr(horse_with_pedigree, "pedigree", None)
        if pedigree is None:
            return None, None, []

        sire_id = pedigree.sire.id if pedigree.sire is not None else None
        dam_id = pedigree.dam.id if pedigree.dam is not None else None
        foal_ids = [foal.id for foal in pedigree.foals]
        return sire_id, dam_id, foal_ids

    @staticmethod
    def _validate_parent_candidate(
        *,
        mode: Literal["sire", "dam"],
        target: Horse,
        target_kind: HorseKindEnum | None,
        parent: Horse,
        parent_kind: HorseKindEnum | None,
        other_parent_id: UUID | None,
        final_foal_ids: set[UUID],
    ) -> None:
        role_title = "Отец" if mode == "sire" else "Мать"
        if parent.id == target.id:
            raise ClientError(f"{role_title} не может совпадать с целевой лошадью")
        if other_parent_id is not None and parent.id == other_parent_id:
            raise ClientError("Отец и мать не могут совпадать")
        if parent.id in final_foal_ids:
            raise ClientError(f"{role_title} не может быть потомком целевой лошади")
        if parent_kind != target_kind:
            raise ClientError(
                f"{role_title} должен быть того же вида, что и целевая лошадь"
            )
        if mode == "sire":
            if parent.sex != HorseSexEnum.MALE:
                raise ClientError("Отец должен быть мужского пола")
            if target.bdate is not None and parent.bdate is not None:
                if parent.bdate >= target.bdate:
                    raise ClientError(
                        "Дата рождения отца должна быть раньше даты рождения целевой лошади"
                    )
            return

        if parent.sex != HorseSexEnum.FEMALE:
            raise ClientError("Мать должна быть женского пола")
        if target.bdate is not None:
            if parent.bdate is not None and parent.bdate >= target.bdate:
                raise ClientError(
                    "Дата рождения матери должна быть раньше даты рождения целевой лошади"
                )
            if parent.ddate is not None and parent.ddate < target.bdate:
                raise ClientError(
                    "Дата смерти матери не может быть раньше даты рождения целевой лошади"
                )

    @staticmethod
    def _validate_child_candidate(
        *,
        target: Horse,
        target_kind: HorseKindEnum | None,
        child: Horse,
        child_kind: HorseKindEnum | None,
        final_parent_ids: set[UUID],
        current_foal_ids: set[UUID],
        allow_existing_foal: bool,
    ) -> None:
        if child.id == target.id:
            raise ClientError("Ребёнок не может совпадать с целевой лошадью")
        if child.id in final_parent_ids:
            raise ClientError("Ребёнок не может совпадать с родителем целевой лошади")
        if child.id in current_foal_ids and not allow_existing_foal:
            raise ClientError("Ребёнок уже указан потомком целевой лошади")
        if child_kind != target_kind:
            raise ClientError("Все дети должны быть того же вида, что и целевая лошадь")
        if target.bdate is not None and child.bdate is not None:
            if child.bdate <= target.bdate:
                raise ClientError(
                    "Дата рождения ребёнка должна быть позже даты рождения целевой лошади"
                )
        if (
            target.sex == HorseSexEnum.FEMALE
            and target.ddate is not None
            and child.bdate is not None
        ):
            if child.bdate > target.ddate:
                raise ClientError(
                    "Дата рождения ребёнка не может быть позже даты смерти матери (целевой лошади)"
                )

    async def create_horse(
        self,
        *,
        create_data: HorseCreateInDto,
        equestrian_context: EquestrianContext,
        user: UserOutDto | None = None,
    ) -> HorseOutDto:
        """Создать новую лошадь."""
        await self._check_admin_permission(user=user, raise_exception=True)
        horse_breed: Breed | None = None
        horse_coat_color: CoatColor | None = None
        horse_owner: HorseOwner | None = None
        if create_data.breed_id is not None:
            horse_breed = await self._get_breed_by_id(
                breed_id=create_data.breed_id, equestrian_context=equestrian_context
            )
        if create_data.coat_color_id is not None:
            horse_coat_color = await self._get_coat_color_by_id(
                coat_color_id=create_data.coat_color_id,
                equestrian_context=equestrian_context,
            )
        if create_data.horse_owner_id is not None:
            horse_owner = await self._get_horse_owner_by_id(
                horse_owner_id=create_data.horse_owner_id,
                equestrian_context=equestrian_context,
            )
        try:
            horse = Horse(
                equestrian_id=equestrian_context.id,
                name=create_data.name,
                code=create_data.code,
                description=create_data.description,
                breed_id=create_data.breed_id,
                coat_color_id=create_data.coat_color_id,
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
        self,
        *,
        horse_id: UUID,
        data: HorseUpdateInDto,
        equestrian_context: EquestrianContext,
        user: UserOutDto | None = None,
    ) -> HorseOutDto:
        """Обновить лошадь."""
        await self._check_admin_permission(user=user, raise_exception=True)
        horse = await self.horse_repository.get_by_id(
            horse_id, equestrian_id=equestrian_context.id
        )
        if horse is None:
            raise ClientError("Лошадь не найдена")
        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            raise ClientError("Нет данных для обновления")
        if "breed_id" in update_data and update_data["breed_id"] is not None:
            await self._get_breed_by_id(
                breed_id=update_data["breed_id"], equestrian_context=equestrian_context
            )
        if "coat_color_id" in update_data and update_data["coat_color_id"] is not None:
            await self._get_coat_color_by_id(
                coat_color_id=update_data["coat_color_id"],
                equestrian_context=equestrian_context,
            )
        if (
            "horse_owner_id" in update_data
            and update_data["horse_owner_id"] is not None
        ):
            await self._get_horse_owner_by_id(
                horse_owner_id=update_data["horse_owner_id"],
                equestrian_context=equestrian_context,
            )
        for key, value in update_data.items():
            setattr(horse, key, value)
        await self.horse_repository.update(horse)
        updated_horse = await self.horse_repository.get_horse_full_info_by_id(
            horse_id=horse.id, equestrian_id=equestrian_context.id
        )
        if updated_horse is None:
            raise ClientError("Лошадь не найдена")
        return HorseOutDto.model_validate(updated_horse)

    async def get_horse_by_slug_or_id(
        self,
        *,
        slug_or_id: str,
        equestrian_context: EquestrianContext,
        pedigree: int | None = None,
        user: UserOutDto | None,
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
                    horse_slug=cast(str, value),
                    equestrian_context=equestrian_context,
                    pedigree=pedigree,
                )
            case "id":
                horse_dto = await self._get_horse_by_id(
                    horse_id=cast(UUID, value),
                    equestrian_context=equestrian_context,
                    pedigree=pedigree,
                )
        return horse_dto

    async def get_available_pedigree(
        self,
        *,
        equestrian_context: EquestrianContext,
        user: UserOutDto | None = None,
        horse_id: UUID,
        mode: Literal["sire", "dam", "children"],
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
        target_horse = await self.horse_repository.get_by_id(
            horse_id, equestrian_id=equestrian_context.id
        )
        if target_horse is None:
            raise ClientError("Лошадь не найдена")
        current_sire_id, current_dam_id, current_foal_ids = (
            await self._get_current_pedigree_ids(
                horse_id=horse_id,
                equestrian_context=equestrian_context,
            )
        )
        exclude_ids = list(
            dict.fromkeys(
                [
                    id_
                    for id_ in (
                        current_sire_id,
                        current_dam_id,
                        *current_foal_ids,
                    )
                    if id_ is not None
                ]
            )
        )
        _PEDIGREE_METHODS_REGISTRY: dict[
            _PedigreeMode,
            Callable[..., Awaitable[tuple[Mapping[UUID, HorseOutDto], int]]],
        ] = {
            "sire": self.horse_repository.get_available_sires,
            "dam": self.horse_repository.get_available_dams,
            "children": self.horse_repository.get_available_children,
        }
        repo_method = _PEDIGREE_METHODS_REGISTRY.get(mode)
        if repo_method is None:
            raise ClientError("Некорректный режим родословной")
        horses, total = await repo_method(
            target_horse=target_horse,
            search=search,
            exclude_ids=exclude_ids,
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
        equestrian_context: EquestrianContext,
        user: UserOutDto | None = None,
    ) -> None:
        """Установить родословное древо лошади."""

        await self._check_admin_permission(user=user, raise_exception=True)

        fields_set = pedigree_data.model_fields_set
        sire_set = "sire_id" in fields_set
        dam_set = "dam_id" in fields_set
        foals_set = "foals" in fields_set
        if not sire_set and not dam_set and not foals_set:
            raise ClientError("Необходимо указать хотя бы одного родителя или потомка")

        if (
            foals_set
            and pedigree_data.foals is not None
            and len(set(pedigree_data.foals)) != len(pedigree_data.foals)
        ):
            raise ClientError("Список потомков содержит дубликаты")

        horses_ids_to_check: list[UUID] = [horse_id]
        if sire_set and pedigree_data.sire_id is not None:
            horses_ids_to_check.append(pedigree_data.sire_id)
        if dam_set and pedigree_data.dam_id is not None:
            horses_ids_to_check.append(pedigree_data.dam_id)
        if foals_set and pedigree_data.foals is not None:
            horses_ids_to_check.extend(pedigree_data.foals)
        horses_ids_to_check_unique = list(dict.fromkeys(horses_ids_to_check))
        horses_mapping: Mapping[UUID, Horse] = await self.horse_repository.get_by_ids(
            horses_ids_to_check_unique, equestrian_id=equestrian_context.id
        )
        if len(horses_mapping) != len(horses_ids_to_check_unique):
            raise ClientError("Некоторые лошади не найдены")

        target = cast(Horse, horses_mapping.get(horse_id))
        breed_kinds = await self._get_breed_kinds_for_horses(
            horses=horses_mapping,
            equestrian_context=equestrian_context,
        )
        target_kind = breed_kinds[target.id]
        current_sire_id, current_dam_id, current_foal_ids = (
            await self._get_current_pedigree_ids(
                horse_id=horse_id,
                equestrian_context=equestrian_context,
            )
        )
        current_foal_ids_set = set(current_foal_ids)

        final_sire_id = pedigree_data.sire_id if sire_set else current_sire_id
        final_dam_id = pedigree_data.dam_id if dam_set else current_dam_id
        final_foal_ids: list[UUID] = (
            pedigree_data.foals or [] if foals_set else current_foal_ids
        )

        if final_sire_id is not None and final_sire_id == final_dam_id:
            raise ClientError("Отец и мать не могут совпадать")
        final_foal_ids_set = set(final_foal_ids)

        if sire_set and pedigree_data.sire_id is not None:
            sire = horses_mapping[pedigree_data.sire_id]
            self._validate_parent_candidate(
                mode="sire",
                target=target,
                target_kind=target_kind,
                parent=sire,
                parent_kind=breed_kinds[sire.id],
                other_parent_id=final_dam_id,
                final_foal_ids=final_foal_ids_set,
            )
        if dam_set and pedigree_data.dam_id is not None:
            dam = horses_mapping[pedigree_data.dam_id]
            self._validate_parent_candidate(
                mode="dam",
                target=target,
                target_kind=target_kind,
                parent=dam,
                parent_kind=breed_kinds[dam.id],
                other_parent_id=final_sire_id,
                final_foal_ids=final_foal_ids_set,
            )
        if foals_set and pedigree_data.foals is not None:
            final_parent_ids = {
                parent_id
                for parent_id in (final_sire_id, final_dam_id)
                if parent_id is not None
            }
            for foal_id in pedigree_data.foals:
                foal = horses_mapping[foal_id]
                self._validate_child_candidate(
                    target=target,
                    target_kind=target_kind,
                    child=foal,
                    child_kind=breed_kinds[foal.id],
                    final_parent_ids=final_parent_ids,
                    current_foal_ids=current_foal_ids_set,
                    allow_existing_foal=foal_id in current_foal_ids_set,
                )

        try:
            await self.horse_children_repository.clear_pedigree(
                target_horse_id=target.id,
                sire=sire_set,
                dam=dam_set,
                foals=foals_set,
            )
            await self.horse_children_repository.set_pedigree(
                target_horse_id=target.id,
                sire_id=pedigree_data.sire_id if sire_set else None,
                dam_id=pedigree_data.dam_id if dam_set else None,
                foals_ids=final_foal_ids if foals_set else None,
            )
        except Exception as ex:
            raise ClientError(
                "Не удалось обновить родословную: операция неатомарна, "
                "после clear_pedigree могли остаться частично очищенные связи"
            ) from ex

    async def delete_horse(
        self,
        *,
        horse_id: UUID,
        equestrian_context: EquestrianContext,
        user: UserOutDto | None = None,
    ) -> None:
        """Удалить лошадь."""
        await self._check_admin_permission(user=user, raise_exception=True)

        horse = await self.horse_repository.get_by_id(
            horse_id, equestrian_id=equestrian_context.id
        )
        if horse is None:
            raise ClientError("Лошадь не найдена")
        await self.horse_repository.delete(
            horse_id, equestrian_id=equestrian_context.id
        )

    async def get_filtered_horses(
        self,
        *,
        equestrian_context: EquestrianContext,
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
        services: list[UUID] | None = None,
        service_names: list[str] | None = None,
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
            equestrian_id=equestrian_context.id,
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
            services=services,
            service_names=service_names,
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

    async def update_horse_photos(
        self,
        *,
        horse_id: UUID,
        data: HorsePhotosUpdateInDto,
        equestrian_context: EquestrianContext,
        user: UserOutDto | None = None,
    ) -> HorseOutDto:
        """Обновить список фотографий лошади (полная замена)."""
        await self._check_admin_permission(user=user, raise_exception=True)

        horse = await self.horse_repository.get_by_id(
            horse_id, equestrian_id=equestrian_context.id
        )
        if horse is None:
            raise ClientError("Лошадь не найдена")

        if self.photo_repository is None:
            raise ClientError("Фото-репозиторий не подключён")

        # Дедупликация и проверка существования фотографий
        unique_ids = list(dict.fromkeys(data.photo_ids))
        if unique_ids:
            existing = await self.photo_repository.get_by_ids(
                unique_ids, equestrian_id=equestrian_context.id
            )
            for photo_id in unique_ids:
                if photo_id not in existing:
                    raise ClientError(f"Фотография с ID '{photo_id}' не найдена")

        await self.horse_repository.set_horse_photos(
            horse_id,
            unique_ids,
            equestrian_id=equestrian_context.id,
        )

        updated = await self.horse_repository.get_horse_full_info_by_id(
            horse_id=horse_id, equestrian_id=equestrian_context.id
        )
        if updated is None:
            raise ClientError("Лошадь не найдена")
        return HorseOutDto.model_validate(updated)

    async def add_horse_service(self):
        """Добавить услугу к лошади."""
        raise ClientError("Функция add_horse_service пока не реализована")

    async def remove_horse_service(self):
        """Удалить услугу из лошади."""
        raise ClientError("Функция remove_horse_service пока не реализована")

    async def update_horse_service(self):
        """Обновить услугу лошади."""
        raise ClientError("Функция update_horse_service пока не реализована")
