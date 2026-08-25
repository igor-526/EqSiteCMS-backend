from datetime import date
from typing import Mapping, Protocol
from uuid import UUID

from core.entities import (
    _HORSE_AVAILABLE_SORT_FIELDS,
    Horse,
    HorseChildren,
    HorseKindEnum,
    HorseSexEnum,
)
from core.schemas import HorseOutDto, HorseWithPedigreeOutDto

from .base_repository import TenantBaseRepositoryProtocol


class HorseSlugConflictError(Exception):
    """The tenant-scoped horse slug unique constraint rejected a mutation."""


class HorseRepositoryProtocol(TenantBaseRepositoryProtocol[Horse], Protocol):
    """Протокол для работы с лошадьми."""

    async def find_by_slug(self, slug: str, *, equestrian_id: UUID) -> Horse | None:
        """Return a horse with this slug in the selected tenant, if any."""
        ...

    async def exists_in_other_tenant(
        self, horse_id: UUID, *, equestrian_id: UUID
    ) -> bool:
        """Return whether the UUID belongs to a different tenant."""
        ...

    async def get_horse_full_info_by_slug(
        self, *, horse_slug: str, equestrian_id: UUID, pedigree: int | None = None
    ) -> HorseOutDto | HorseWithPedigreeOutDto | None:
        """Получить полную информацию о лошади c породой, мастью, владельцем, фотографиями и услугами"""
        ...

    async def get_horse_full_info_by_id(
        self, *, horse_id: UUID, equestrian_id: UUID, pedigree: int | None = None
    ) -> HorseOutDto | HorseWithPedigreeOutDto | None:
        """Получить полную информацию о лошади c породой, мастью, владельцем, фотографиями и услугами"""
        ...

    async def get_horse_list_full_info(
        self,
        *,
        equestrian_id: UUID,
        name: str | None = None,
        description: str | None = None,
        breed_ids: list[UUID] | None = None,
        breed_id_is_null: bool | None = None,
        coat_color_ids: list[UUID] | None = None,
        kind: list[HorseKindEnum] | None = None,
        height_gte: int | None = None,
        height_lte: int | None = None,
        sex: list[HorseSexEnum] | None = None,
        bdate_gte: date | None = None,
        bdate_lte: date | None = None,
        bdate_gt_or_none: date | None = None,
        bdate_lt_or_none: date | None = None,
        bdate_gte_or_none: date | None = None,
        bdate_lte_or_none: date | None = None,
        ddate_gte: date | None = None,
        ddate_lte: date | None = None,
        ddate_gte_or_none: date | None = None,
        ddate_lte_or_none: date | None = None,
        horse_owner_ids: list[UUID] | None = None,
        services: list[UUID] | None = None,
        service_names: list[str] | None = None,
        this_stable: bool | None = None,
        exclude_ids: list[UUID] | None = None,
        include_ids: list[UUID] | None = None,
        exclude_ids_that_are_children_of_sex: list[HorseSexEnum] | None = None,
        limit: int | None = None,
        offset: int | None = None,
        sort: list[_HORSE_AVAILABLE_SORT_FIELDS] | None = None,
        pedigree: int | None = None,
    ) -> tuple[Mapping[UUID, HorseOutDto | HorseWithPedigreeOutDto], int]:
        """Получить полную информацию о лошадях.

        Query ``kind`` остается контрактом списка лошадей, но реализация
        фильтрует и сортирует по ``breeds.kind``, а не по полю лошади.
        ``services`` использует OR-семантику внутри tenant-scoped ``EXISTS``.
        """
        ...

    async def get_available_dams(
        self,
        *,
        target_horse: Horse,
        search: str | None = None,
        exclude_ids: list[UUID] | None = None,
        limit: int | None = 25,
        offset: int | None = 0,
    ) -> tuple[Mapping[UUID, HorseOutDto], int]:
        """Получить доступных матерей."""
        ...

    async def get_available_sires(
        self,
        *,
        target_horse: Horse,
        search: str | None = None,
        exclude_ids: list[UUID] | None = None,
        limit: int | None = 25,
        offset: int | None = 0,
    ) -> tuple[Mapping[UUID, HorseOutDto], int]:
        """Получить доступных отцов."""
        ...

    async def get_available_children(
        self,
        *,
        target_horse: Horse,
        search: str | None = None,
        exclude_ids: list[UUID] | None = None,
        limit: int | None = 25,
        offset: int | None = 0,
    ) -> tuple[Mapping[UUID, HorseOutDto], int]:
        """Получить доступных детей."""
        ...

    async def set_horse_photos(
        self,
        horse_id: UUID,
        photo_ids: list[UUID],
        main_photo_id: UUID | None = None,
        *,
        equestrian_id: UUID,
    ) -> None:
        """Заменить список фотографий лошади."""
        ...


class HorseChildrenRepositoryProtocol(
    TenantBaseRepositoryProtocol[HorseChildren], Protocol
):
    """Протокол для работы с родословной лошади (связи родитель–потомок)."""

    async def clear_pedigree(
        self,
        *,
        target_horse_id: UUID,
        sire: bool = False,
        dam: bool = False,
        foals: bool | list[UUID] = False,
    ) -> None:
        """Очистить родословное древо лошади."""
        ...

    async def set_pedigree(
        self,
        *,
        target_horse_id: UUID,
        sire_id: UUID | None = None,
        dam_id: UUID | None = None,
        foals_ids: list[UUID] | None = None,
    ) -> None:
        """Установить родословное древо лошади."""
        ...
