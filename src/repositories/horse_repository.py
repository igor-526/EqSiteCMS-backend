import re
from datetime import date
from typing import Mapping, Union
from uuid import UUID

from sqlalchemy import Table, and_, delete, exists, func, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from core.entities import (
    _HORSE_AVAILABLE_SORT_FIELDS,
    Horse,
    HorseChildren,
    HorseDateModeEnum,
    HorseKindEnum,
    HorseSexEnum,
)
from core.protocols.media import PhotoUrlBuilderProtocol
from core.schemas import (
    BreedOutDto,
    CoatColorOutDto,
    FoalParentRefDto,
    FoalParentsDto,
    HorseFoalOutDto,
    HorseOutDto,
    HorseOwnerOutDto,
    HorsePedigree,
    HorseServiceOutDto,
    HorseWithPedigreeOutDto,
    PhotoOutShortDto,
)
from models.breeds import breeds
from models.coat_color import coat_color
from models.horse import horse, horse_children, horse_photos
from models.horse_owner import horse_owner
from models.horse_service import horse_service, horse_service_relations
from models.photos import photos

from .abstract_repository import TenantScopedRepository

# Explicit column label prefixes for JOIN queries.
# breeds and coat_color share columns (short_name, page_data) that are NOT in
# the horse table.  SQLAlchemy auto-deduplication assigns those columns the
# same _1 suffix for both tables, so reading them with a suffix heuristic is
# ambiguous.  We avoid that by using unambiguous per-table prefixes in SELECT.
_BREED_PREFIX = "breed__"
_COAT_COLOR_PREFIX = "coat_color__"
_HORSE_OWNER_PREFIX = "horse_owner__"


def _labeled_columns(table: Table, prefix: str) -> list:
    """Return a list of explicitly labeled column expressions for *table*."""
    return [c.label(f"{prefix}{c.key}") for c in table.c]


def _extract_prefixed(row: Mapping, prefix: str, table: Table) -> dict | None:
    """Extract a table's columns from a JOIN row using explicit *prefix* labels.

    Returns ``None`` when the primary-key column is NULL (LEFT JOIN miss).
    """
    pk_key = f"{prefix}id"
    if row.get(pk_key) is None:
        return None
    return {
        c.key: row[f"{prefix}{c.key}"] for c in table.c if f"{prefix}{c.key}" in row
    }


class HorseRepository(TenantScopedRepository[Horse]):
    """Репозиторий для работы с лошадьми."""

    table: Table = horse
    entity = Horse

    def __init__(
        self,
        session: AsyncSession,
        photo_url_builder: PhotoUrlBuilderProtocol,
    ) -> None:
        super().__init__(session=session)
        self.photo_url_builder = photo_url_builder

    @staticmethod
    def _row_to_joined_table(row: Mapping, table: Table, suffixes: list[str]) -> dict:
        """Извлекает данные таблицы из строки join'а (ключи — строки с суффиксами _1, _2, _3)."""
        result = {}
        for c in table.c:
            for suffix in suffixes:
                key = f"{c.key}{suffix}" if suffix else c.key
                if key in row:
                    result[c.key] = row[key]
                    break
        return result

    def _build_horse_dto(
        self,
        horse_data: dict,
        breed_data: dict | None,
        coat_color_data: dict | None,
        horse_owner_data: dict | None,
        photos_data: list[dict],
        services_data: list[dict],
    ) -> HorseOutDto:
        breed_dto = BreedOutDto(**breed_data) if breed_data else None
        coat_color_dto = CoatColorOutDto(**coat_color_data) if coat_color_data else None
        horse_owner_dto = (
            HorseOwnerOutDto(**horse_owner_data) if horse_owner_data else None
        )

        photos_dto = [
            PhotoOutShortDto(
                id=UUID(str(photo["photo_id"])),
                is_main=photo["is_main"],
                url=self.photo_url_builder.build(photo["path"]),
            )
            for photo in photos_data
        ]

        services_dto = [
            HorseServiceOutDto(
                id=service["id"],
                name=service["name"],
                slug=service["slug"],
                description=(
                    service.get("description_override")
                    if service.get("description_override") is not None
                    else service.get("description")
                ),
                price=(
                    service.get("price_override")
                    if service.get("price_override") is not None
                    else service["price"]
                ),
                price_formatter=(
                    service.get("price_formatter_override")
                    if service.get("price_formatter_override") is not None
                    else service["price_formatter"]
                ),
                created_at=service["created_at"],
                updated_at=service.get("updated_at"),
            )
            for service in services_data
        ]

        return HorseOutDto(
            id=horse_data["id"],
            slug=horse_data.get("slug") or "",
            name=horse_data["name"],
            pedigree_name=horse_data.get("pedigree_name"),
            description=horse_data.get("description"),
            breed=breed_dto,
            coat_color=coat_color_dto,
            height=horse_data.get("height"),
            sex=HorseSexEnum(horse_data["sex"]),
            bdate=horse_data.get("bdate"),
            ddate=horse_data.get("ddate"),
            bdate_mode=HorseDateModeEnum(horse_data.get("bdate_mode", "hide")),
            ddate_mode=HorseDateModeEnum(horse_data.get("ddate_mode", "hide")),
            horse_owner=horse_owner_dto,
            photos=photos_dto,
            services=services_dto,
            this_stable=horse_data.get("this_stable", False),
        )

    async def get_horse_full_info_by_slug(
        self, *, horse_slug: str, equestrian_id: UUID, pedigree: int | None = None
    ) -> HorseOutDto | HorseWithPedigreeOutDto | None:
        if pedigree is not None and pedigree > 0:
            id_stmt = select(horse.c.id).where(
                horse.c.slug == horse_slug,
                horse.c.equestrian_id == equestrian_id,
            )
            id_result = await self.session.execute(id_stmt)
            id_row = id_result.first()
            if id_row is None:
                return None
            horse_id = UUID(str(id_row[0]))
            mapping, _ = await self.get_horse_list_full_info(
                include_ids=[horse_id],
                equestrian_id=equestrian_id,
                limit=1,
                pedigree=pedigree,
            )
            return mapping.get(horse_id) if mapping else None

        stmt = (
            select(
                horse,
                *_labeled_columns(breeds, _BREED_PREFIX),
                *_labeled_columns(coat_color, _COAT_COLOR_PREFIX),
                *_labeled_columns(horse_owner, _HORSE_OWNER_PREFIX),
            )
            .outerjoin(
                breeds,
                and_(
                    horse.c.breed_id == breeds.c.id,
                    breeds.c.equestrian_id == equestrian_id,
                ),
            )
            .outerjoin(
                coat_color,
                and_(
                    horse.c.coat_color_id == coat_color.c.id,
                    coat_color.c.equestrian_id == equestrian_id,
                ),
            )
            .outerjoin(
                horse_owner,
                and_(
                    horse.c.horse_owner_id == horse_owner.c.id,
                    horse_owner.c.equestrian_id == equestrian_id,
                ),
            )
            .where(horse.c.slug == horse_slug, horse.c.equestrian_id == equestrian_id)
        )

        result = await self.session.execute(stmt)
        row = result.mappings().first()

        if row is None:
            return None

        horse_id = UUID(str(row["id"]))
        horse_keys = {c.key for c in horse.c}
        horse_data = {k: v for k, v in row.items() if k in horse_keys}
        breed_data = _extract_prefixed(row, _BREED_PREFIX, breeds)
        coat_color_data = _extract_prefixed(row, _COAT_COLOR_PREFIX, coat_color)
        horse_owner_data = _extract_prefixed(row, _HORSE_OWNER_PREFIX, horse_owner)

        photos_stmt = (
            select(horse_photos.c.photo_id, horse_photos.c.is_main, photos.c.path)
            .join(photos, horse_photos.c.photo_id == photos.c.id)
            .where(
                horse_photos.c.horse_id == horse_id,
                photos.c.equestrian_id == equestrian_id,
            )
        )
        photos_result = await self.session.execute(photos_stmt)
        photos_data = [dict(row) for row in photos_result.mappings().all()]

        services_stmt = (
            select(
                horse_service,
                horse_service_relations.c.description_override,
                horse_service_relations.c.price_override,
                horse_service_relations.c.price_formatter_override,
            )
            .join(
                horse_service_relations,
                horse_service.c.id == horse_service_relations.c.service_id,
            )
            .where(
                horse_service_relations.c.horse_id == horse_id,
                horse_service.c.equestrian_id == equestrian_id,
            )
        )
        services_result = await self.session.execute(services_stmt)
        services_data = [dict(row) for row in services_result.mappings().all()]

        return self._build_horse_dto(
            horse_data,
            breed_data,
            coat_color_data,
            horse_owner_data,
            photos_data,
            services_data,
        )

    async def get_horse_full_info_by_id(
        self, *, horse_id: UUID, equestrian_id: UUID, pedigree: int | None = None
    ) -> HorseOutDto | HorseWithPedigreeOutDto | None:
        if pedigree is not None and pedigree > 0:
            mapping, _ = await self.get_horse_list_full_info(
                include_ids=[horse_id],
                equestrian_id=equestrian_id,
                limit=1,
                pedigree=pedigree,
            )
            return mapping.get(horse_id) if mapping else None

        stmt = (
            select(
                horse,
                *_labeled_columns(breeds, _BREED_PREFIX),
                *_labeled_columns(coat_color, _COAT_COLOR_PREFIX),
                *_labeled_columns(horse_owner, _HORSE_OWNER_PREFIX),
            )
            .outerjoin(
                breeds,
                and_(
                    horse.c.breed_id == breeds.c.id,
                    breeds.c.equestrian_id == equestrian_id,
                ),
            )
            .outerjoin(
                coat_color,
                and_(
                    horse.c.coat_color_id == coat_color.c.id,
                    coat_color.c.equestrian_id == equestrian_id,
                ),
            )
            .outerjoin(
                horse_owner,
                and_(
                    horse.c.horse_owner_id == horse_owner.c.id,
                    horse_owner.c.equestrian_id == equestrian_id,
                ),
            )
            .where(horse.c.id == horse_id, horse.c.equestrian_id == equestrian_id)
        )

        result = await self.session.execute(stmt)
        row = result.mappings().first()

        if row is None:
            return None

        horse_keys = {c.key for c in horse.c}
        horse_data = {k: v for k, v in row.items() if k in horse_keys}
        breed_data = _extract_prefixed(row, _BREED_PREFIX, breeds)
        coat_color_data = _extract_prefixed(row, _COAT_COLOR_PREFIX, coat_color)
        horse_owner_data = _extract_prefixed(row, _HORSE_OWNER_PREFIX, horse_owner)

        photos_stmt = (
            select(horse_photos.c.photo_id, horse_photos.c.is_main, photos.c.path)
            .join(photos, horse_photos.c.photo_id == photos.c.id)
            .where(
                horse_photos.c.horse_id == horse_id,
                photos.c.equestrian_id == equestrian_id,
            )
        )
        photos_result = await self.session.execute(photos_stmt)
        photos_data = [dict(row) for row in photos_result.mappings().all()]

        services_stmt = (
            select(
                horse_service,
                horse_service_relations.c.description_override,
                horse_service_relations.c.price_override,
                horse_service_relations.c.price_formatter_override,
            )
            .join(
                horse_service_relations,
                horse_service.c.id == horse_service_relations.c.service_id,
            )
            .where(
                horse_service_relations.c.horse_id == horse_id,
                horse_service.c.equestrian_id == equestrian_id,
            )
        )
        services_result = await self.session.execute(services_stmt)
        services_data = [dict(row) for row in services_result.mappings().all()]

        return self._build_horse_dto(
            horse_data,
            breed_data,
            coat_color_data,
            horse_owner_data,
            photos_data,
            services_data,
        )

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
    ) -> tuple[Mapping[UUID, Union[HorseOutDto, HorseWithPedigreeOutDto]], int]:
        base_stmt = (
            select(
                horse,
                *_labeled_columns(breeds, _BREED_PREFIX),
                *_labeled_columns(coat_color, _COAT_COLOR_PREFIX),
                *_labeled_columns(horse_owner, _HORSE_OWNER_PREFIX),
            )
            .outerjoin(
                breeds,
                and_(
                    horse.c.breed_id == breeds.c.id,
                    breeds.c.equestrian_id == equestrian_id,
                ),
            )
            .outerjoin(
                coat_color,
                and_(
                    horse.c.coat_color_id == coat_color.c.id,
                    coat_color.c.equestrian_id == equestrian_id,
                ),
            )
            .outerjoin(
                horse_owner,
                and_(
                    horse.c.horse_owner_id == horse_owner.c.id,
                    horse_owner.c.equestrian_id == equestrian_id,
                ),
            )
        )

        count_stmt = select(func.count(func.distinct(horse.c.id))).select_from(
            horse.outerjoin(
                breeds,
                and_(
                    horse.c.breed_id == breeds.c.id,
                    breeds.c.equestrian_id == equestrian_id,
                ),
            )
            .outerjoin(
                coat_color,
                and_(
                    horse.c.coat_color_id == coat_color.c.id,
                    coat_color.c.equestrian_id == equestrian_id,
                ),
            )
            .outerjoin(
                horse_owner,
                and_(
                    horse.c.horse_owner_id == horse_owner.c.id,
                    horse_owner.c.equestrian_id == equestrian_id,
                ),
            )
        )

        conditions: list[ColumnElement[bool]] = [horse.c.equestrian_id == equestrian_id]
        if name:
            safe = re.escape(name)
            conditions.append(horse.c.name.op("~*")(safe))
        if description:
            safe = re.escape(description)
            conditions.append(horse.c.description.op("~*")(safe))
        if breed_ids:
            conditions.append(horse.c.breed_id.in_(breed_ids))
        if breed_id_is_null is True:
            conditions.append(horse.c.breed_id.is_(None))
        if coat_color_ids:
            conditions.append(horse.c.coat_color_id.in_(coat_color_ids))
        if kind:
            conditions.append(breeds.c.kind.in_([k.value for k in kind]))
        if height_gte is not None:
            conditions.append(horse.c.height >= height_gte)
        if height_lte is not None:
            conditions.append(horse.c.height <= height_lte)
        if sex:
            conditions.append(horse.c.sex.in_([s.value for s in sex]))
        if bdate_gte is not None:
            conditions.append(horse.c.bdate >= bdate_gte)
        if bdate_lte is not None:
            conditions.append(horse.c.bdate <= bdate_lte)
        if bdate_gt_or_none is not None:
            conditions.append(
                or_(horse.c.bdate > bdate_gt_or_none, horse.c.bdate.is_(None))
            )
        if bdate_lt_or_none is not None:
            conditions.append(
                or_(horse.c.bdate < bdate_lt_or_none, horse.c.bdate.is_(None))
            )
        if bdate_gte_or_none is not None:
            conditions.append(
                or_(horse.c.bdate >= bdate_gte_or_none, horse.c.bdate.is_(None))
            )
        if bdate_lte_or_none is not None:
            conditions.append(
                or_(horse.c.bdate <= bdate_lte_or_none, horse.c.bdate.is_(None))
            )
        if ddate_gte is not None:
            conditions.append(horse.c.ddate >= ddate_gte)
        if ddate_lte is not None:
            conditions.append(horse.c.ddate <= ddate_lte)
        if ddate_gte_or_none is not None:
            conditions.append(
                or_(horse.c.ddate >= ddate_gte_or_none, horse.c.ddate.is_(None))
            )
        if ddate_lte_or_none is not None:
            conditions.append(
                or_(horse.c.ddate <= ddate_lte_or_none, horse.c.ddate.is_(None))
            )
        if horse_owner_ids:
            conditions.append(horse.c.horse_owner_id.in_(horse_owner_ids))
        if services:
            service_ids = list(dict.fromkeys(services))
            service_match = (
                select(1)
                .select_from(
                    horse_service_relations.join(
                        horse_service,
                        horse_service.c.id == horse_service_relations.c.service_id,
                    )
                )
                .where(
                    horse_service_relations.c.horse_id == horse.c.id,
                    horse_service.c.equestrian_id == equestrian_id,
                    horse_service.c.id.in_(service_ids),
                )
            )
            conditions.append(exists(service_match))
        if service_names:
            # Фильтрация по наименованиям услуг (регистронезависимое полное совпадение)
            service_names_lower = [
                name.lower().strip() for name in service_names if name.strip()
            ]
            if service_names_lower:
                service_name_match = (
                    select(1)
                    .select_from(
                        horse_service_relations.join(
                            horse_service,
                            horse_service.c.id == horse_service_relations.c.service_id,
                        )
                    )
                    .where(
                        horse_service_relations.c.horse_id == horse.c.id,
                        horse_service.c.equestrian_id == equestrian_id,
                        func.lower(horse_service.c.name).in_(service_names_lower),
                    )
                )
                conditions.append(exists(service_name_match))
        if this_stable is not None:
            conditions.append(horse.c.this_stable == this_stable)
        if exclude_ids:
            conditions.append(~horse.c.id.in_(exclude_ids))
        if include_ids:
            conditions.append(horse.c.id.in_(include_ids))
        if exclude_ids_that_are_children_of_sex:
            subq = (
                select(horse_children.c.child_id)
                .join(horse, horse_children.c.horse_id == horse.c.id)
                .where(
                    horse.c.equestrian_id == equestrian_id,
                    horse.c.sex.in_(
                        [e.value for e in exclude_ids_that_are_children_of_sex]
                    ),
                )
            )
            conditions.append(~horse.c.id.in_(subq))

        if conditions:
            where_clause = and_(*conditions)
            base_stmt = base_stmt.where(where_clause)
            count_stmt = count_stmt.where(where_clause)

        if sort:
            order_by_clauses = []
            for field in sort:
                field_name = field[1:] if field.startswith("-") else field
                if field_name == "breed_name":
                    column = breeds.c.short_name
                elif field_name == "coat_color_name":
                    column = coat_color.c.short_name
                elif field_name == "kind":
                    column = breeds.c.kind
                else:
                    column = horse.c[field_name]

                if field.startswith("-"):
                    order_by_clauses.append(column.desc().nulls_last())
                else:
                    order_by_clauses.append(column.asc().nulls_first())
            base_stmt = base_stmt.order_by(*order_by_clauses)
        else:
            base_stmt = base_stmt.order_by(
                horse.c.updated_at.desc().nulls_last(),
                horse.c.created_at.desc().nulls_last(),
            )

        if limit is not None:
            base_stmt = base_stmt.limit(limit)
        if offset is not None:
            base_stmt = base_stmt.offset(offset)

        base_result = await self.session.execute(base_stmt)
        rows = base_result.mappings().all()

        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        horse_ids = [UUID(str(row["id"])) for row in rows]

        if not horse_ids:
            return {}, total

        photos_stmt = (
            select(
                horse_photos.c.horse_id,
                horse_photos.c.photo_id,
                horse_photos.c.is_main,
                photos.c.path,
            )
            .join(photos, horse_photos.c.photo_id == photos.c.id)
            .where(
                horse_photos.c.horse_id.in_(horse_ids),
                photos.c.equestrian_id == equestrian_id,
            )
        )
        photos_result = await self.session.execute(photos_stmt)
        photos_by_horse: dict[UUID, list[dict]] = {}
        for row in photos_result.mappings().all():
            horse_id = UUID(str(row["horse_id"]))
            if horse_id not in photos_by_horse:
                photos_by_horse[horse_id] = []
            photos_by_horse[horse_id].append(dict(row))

        services_stmt = (
            select(
                horse_service,
                horse_service_relations.c.horse_id,
                horse_service_relations.c.description_override,
                horse_service_relations.c.price_override,
                horse_service_relations.c.price_formatter_override,
            )
            .join(
                horse_service_relations,
                horse_service.c.id == horse_service_relations.c.service_id,
            )
            .where(horse_service_relations.c.horse_id.in_(horse_ids))
            .where(horse_service.c.equestrian_id == equestrian_id)
        )
        services_result = await self.session.execute(services_stmt)
        services_by_horse: dict[UUID, list[dict]] = {}
        horse_service_keys = {c.key for c in horse_service.c}
        override_keys = {
            "description_override",
            "price_override",
            "price_formatter_override",
        }
        for row in services_result.mappings().all():
            horse_id = UUID(str(row["horse_id"]))
            if horse_id not in services_by_horse:
                services_by_horse[horse_id] = []
            service_data = {
                k: v
                for k, v in row.items()
                if k in horse_service_keys or k in override_keys
            }
            services_by_horse[horse_id].append(service_data)

        horses_dict: dict[UUID, HorseOutDto] = {}
        horse_keys = {c.key for c in horse.c}
        for row in rows:
            horse_id = UUID(str(row["id"]))
            horse_data = {k: v for k, v in row.items() if k in horse_keys}
            breed_data = _extract_prefixed(row, _BREED_PREFIX, breeds)
            coat_color_data = _extract_prefixed(row, _COAT_COLOR_PREFIX, coat_color)
            horse_owner_data = _extract_prefixed(row, _HORSE_OWNER_PREFIX, horse_owner)

            photos_data = photos_by_horse.get(horse_id, [])
            services_data = services_by_horse.get(horse_id, [])

            horses_dict[horse_id] = self._build_horse_dto(
                horse_data,
                breed_data,
                coat_color_data,
                horse_owner_data,
                photos_data,
                services_data,
            )

        if pedigree and pedigree > 0:
            sire_by_horse: dict[UUID, UUID] = {}
            dam_by_horse: dict[UUID, UUID] = {}
            foals_by_horse: dict[UUID, list[UUID]] = {}

            current_children: set[UUID] = set(horse_ids)
            for _ in range(pedigree):
                if not current_children:
                    break
                parents_stmt = (
                    select(
                        horse_children.c.child_id,
                        horse_children.c.horse_id,
                        horse.c.sex,
                    )
                    .join(horse, horse_children.c.horse_id == horse.c.id)
                    .where(
                        horse_children.c.child_id.in_(current_children),
                        horse.c.equestrian_id == equestrian_id,
                    )
                )
                parents_result = await self.session.execute(parents_stmt)
                next_children: set[UUID] = set()
                for row in parents_result.mappings().all():
                    child_id = UUID(str(row["child_id"]))
                    parent_id = UUID(str(row["horse_id"]))
                    sex = row["sex"]
                    if sex in (HorseSexEnum.MALE.value, HorseSexEnum.GELD.value):
                        sire_by_horse[child_id] = parent_id
                        next_children.add(parent_id)
                    elif sex == HorseSexEnum.FEMALE.value:
                        dam_by_horse[child_id] = parent_id
                        next_children.add(parent_id)
                current_children = next_children

            foals_stmt = select(
                horse_children.c.horse_id,
                horse_children.c.child_id,
            ).where(horse_children.c.horse_id.in_(horse_ids))
            foals_result = await self.session.execute(foals_stmt)
            for row in foals_result.mappings().all():
                parent_id = UUID(str(row["horse_id"]))
                child_id = UUID(str(row["child_id"]))
                if parent_id not in foals_by_horse:
                    foals_by_horse[parent_id] = []
                foals_by_horse[parent_id].append(child_id)

            # Собираем всех жеребят для поиска их производителей
            all_foal_ids: set[UUID] = {
                foal_id
                for foal_list in foals_by_horse.values()
                for foal_id in foal_list
            }

            foal_sire_by_foal: dict[UUID, UUID] = {}
            foal_dam_by_foal: dict[UUID, UUID] = {}

            if all_foal_ids:
                foal_parents_stmt = (
                    select(
                        horse_children.c.child_id,
                        horse_children.c.horse_id,
                        horse.c.sex,
                    )
                    .join(horse, horse_children.c.horse_id == horse.c.id)
                    .where(
                        horse_children.c.child_id.in_(all_foal_ids),
                        horse.c.equestrian_id == equestrian_id,
                    )
                )
                foal_parents_result = await self.session.execute(foal_parents_stmt)
                for row in foal_parents_result.mappings().all():
                    child_id = UUID(str(row["child_id"]))
                    parent_id = UUID(str(row["horse_id"]))
                    sex = row["sex"]
                    if sex in (HorseSexEnum.MALE.value, HorseSexEnum.GELD.value):
                        foal_sire_by_foal[child_id] = parent_id
                    elif sex == HorseSexEnum.FEMALE.value:
                        foal_dam_by_foal[child_id] = parent_id

            pedigree_ids: set[UUID] = (
                set(horse_ids)
                | set(sire_by_horse.values())
                | set(dam_by_horse.values())
                | {f for fs in foals_by_horse.values() for f in fs}
                | set(foal_sire_by_foal.values())
                | set(foal_dam_by_foal.values())
            )
            missing_ids = pedigree_ids - set(horses_dict.keys())

            all_dtos: dict[UUID, HorseOutDto] = dict(horses_dict)
            batch_size = 50
            if missing_ids:
                missing_list = list(missing_ids)
                for i in range(0, len(missing_list), batch_size):
                    batch = missing_list[i : i + batch_size]
                    fetched, _ = await self.get_horse_list_full_info(
                        include_ids=batch,
                        equestrian_id=equestrian_id,
                        limit=len(batch) + 1,
                        pedigree=0,
                    )
                    all_dtos.update(fetched)

            top_level_ids = set(horse_ids)

            def make_foal_parent_ref(parent_id: UUID | None) -> FoalParentRefDto | None:
                if parent_id is None:
                    return None
                dto = all_dtos.get(parent_id)
                if dto is None:
                    return None
                return FoalParentRefDto(
                    id=dto.id, name=dto.name, pedigree_name=dto.pedigree_name
                )

            def build_pedigree_dto(
                h_id: UUID,
                generations_left: int,
            ) -> HorseOutDto | HorseWithPedigreeOutDto | None:
                base_dto = all_dtos.get(h_id)
                if base_dto is None:
                    return None
                if generations_left <= 0:
                    return base_dto
                sire_id = sire_by_horse.get(h_id)
                dam_id = dam_by_horse.get(h_id)
                sire_dto = (
                    build_pedigree_dto(sire_id, generations_left - 1)
                    if sire_id
                    else None
                )
                dam_dto = (
                    build_pedigree_dto(dam_id, generations_left - 1) if dam_id else None
                )
                foals_dtos = (
                    [
                        HorseFoalOutDto(
                            **all_dtos[f].model_dump(),
                            parents=FoalParentsDto(
                                sire=make_foal_parent_ref(foal_sire_by_foal.get(f)),
                                dam=make_foal_parent_ref(foal_dam_by_foal.get(f)),
                            ),
                        )
                        for f in foals_by_horse.get(h_id, [])
                        if f in all_dtos
                    ]
                    if h_id in top_level_ids
                    else []
                )
                return HorseWithPedigreeOutDto(
                    **base_dto.model_dump(),
                    pedigree=HorsePedigree(
                        sire=sire_dto,
                        dam=dam_dto,
                        foals=foals_dtos,
                    ),
                )

            result_dict: dict[UUID, HorseWithPedigreeOutDto] = {}
            for h_id in horse_ids:
                built = build_pedigree_dto(h_id, pedigree)
                if isinstance(built, HorseWithPedigreeOutDto):
                    result_dict[h_id] = built
                elif built is not None:
                    result_dict[h_id] = HorseWithPedigreeOutDto(
                        **built.model_dump(),
                        pedigree=HorsePedigree(
                            sire=None,
                            dam=None,
                            foals=[
                                HorseFoalOutDto(
                                    **all_dtos[f].model_dump(),
                                    parents=FoalParentsDto(
                                        sire=make_foal_parent_ref(
                                            foal_sire_by_foal.get(f)
                                        ),
                                        dam=make_foal_parent_ref(
                                            foal_dam_by_foal.get(f)
                                        ),
                                    ),
                                )
                                for f in foals_by_horse.get(h_id, [])
                                if f in all_dtos
                            ],
                        ),
                    )
                else:
                    base = horses_dict.get(h_id)
                    if base is not None:
                        result_dict[h_id] = HorseWithPedigreeOutDto(
                            **base.model_dump(),
                            pedigree=HorsePedigree(
                                sire=None,
                                dam=None,
                                foals=[],
                            ),
                        )
            return result_dict, total

        return horses_dict, total

    async def _get_breed_kind_for_horse(
        self, *, target_horse: Horse
    ) -> HorseKindEnum | None:
        if target_horse.breed_id is None:
            return None
        stmt = select(breeds.c.kind).where(
            breeds.c.id == target_horse.breed_id,
            breeds.c.equestrian_id == target_horse.equestrian_id,
        )
        result = await self.session.execute(stmt)
        value = result.scalar_one_or_none()
        return HorseKindEnum(value) if value is not None else None

    async def set_horse_photos(
        self,
        horse_id: UUID,
        photo_ids: list[UUID],
        main_photo_id: UUID | None = None,
        *,
        equestrian_id: UUID,
    ) -> None:
        """Заменить список фотографий лошади (полная замена связей)."""
        # Удаляем все существующие связи для этой лошади
        delete_stmt = delete(horse_photos).where(
            horse_photos.c.horse_id == horse_id,
            horse_photos.c.horse_id.in_(
                select(horse.c.id).where(horse.c.equestrian_id == equestrian_id)
            ),
        )
        await self.session.execute(delete_stmt)

        # Вставляем новые связи
        if photo_ids:
            values = [
                {
                    "horse_id": horse_id,
                    "photo_id": photo_id,
                    "is_main": photo_id == main_photo_id,
                }
                for photo_id in photo_ids
            ]
            insert_stmt = insert(horse_photos).values(values)
            await self.session.execute(insert_stmt)

        await self.session.flush()

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
        target_breed_kind = await self._get_breed_kind_for_horse(
            target_horse=target_horse
        )
        filters: dict = {
            "equestrian_id": target_horse.equestrian_id,
            "sex": [HorseSexEnum.FEMALE],
            "exclude_ids": list(dict.fromkeys([target_horse.id, *(exclude_ids or [])])),
            "sort": ["name"],
            "limit": limit,
            "offset": offset,
        }
        if target_breed_kind is not None:
            filters["kind"] = [target_breed_kind]
        else:
            filters["breed_id_is_null"] = True
        if search:
            filters["name"] = search
        if target_horse.bdate is not None:
            filters["bdate_lt_or_none"] = target_horse.bdate
            filters["ddate_gte_or_none"] = target_horse.bdate
        return await self.get_horse_list_full_info(**filters)

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
        target_breed_kind = await self._get_breed_kind_for_horse(
            target_horse=target_horse
        )
        filters: dict = {
            "equestrian_id": target_horse.equestrian_id,
            "sex": [HorseSexEnum.MALE],
            "exclude_ids": list(dict.fromkeys([target_horse.id, *(exclude_ids or [])])),
            "sort": ["name"],
            "limit": limit,
            "offset": offset,
        }
        if target_breed_kind is not None:
            filters["kind"] = [target_breed_kind]
        else:
            filters["breed_id_is_null"] = True
        if search:
            filters["name"] = search
        if target_horse.bdate is not None:
            filters["bdate_lt_or_none"] = target_horse.bdate
        return await self.get_horse_list_full_info(**filters)

    async def get_available_children(
        self,
        *,
        target_horse: Horse,
        search: str | None = None,
        exclude_ids: list[UUID] | None = None,
        limit: int | None = 25,
        offset: int | None = 0,
    ) -> tuple[Mapping[UUID, HorseOutDto], int]:
        """Получить доступных детей (без дублирования отца/матери: исключаем уже имеющих родителя того же пола)."""
        target_breed_kind = await self._get_breed_kind_for_horse(
            target_horse=target_horse
        )
        filters: dict = {
            "equestrian_id": target_horse.equestrian_id,
            "exclude_ids": list(dict.fromkeys([target_horse.id, *(exclude_ids or [])])),
            "sort": ["name"],
            "limit": limit,
            "offset": offset,
        }
        if target_breed_kind is not None:
            filters["kind"] = [target_breed_kind]
        else:
            filters["breed_id_is_null"] = True
        if search:
            filters["name"] = search
        if target_horse.bdate is not None:
            filters["bdate_gt_or_none"] = target_horse.bdate
        if target_horse.sex == HorseSexEnum.FEMALE and target_horse.ddate is not None:
            filters["bdate_lte_or_none"] = target_horse.ddate
        if target_horse.sex == HorseSexEnum.FEMALE:
            filters["exclude_ids_that_are_children_of_sex"] = [HorseSexEnum.FEMALE]
        elif target_horse.sex in (HorseSexEnum.MALE, HorseSexEnum.GELD):
            filters["exclude_ids_that_are_children_of_sex"] = [
                HorseSexEnum.MALE,
                HorseSexEnum.GELD,
            ]
        return await self.get_horse_list_full_info(**filters)


class HorseChildrenRepository(TenantScopedRepository[HorseChildren]):
    """Репозиторий для работы с родословной лошади (связи родитель–потомок)."""

    table: Table = horse_children
    entity = HorseChildren

    async def clear_pedigree(
        self,
        *,
        target_horse_id: UUID,
        sire: bool = False,
        dam: bool = False,
        foals: bool | list[UUID] = False,
    ) -> None:
        """Очистить родословное древо лошади."""
        if sire:
            sire_parents = select(horse.c.id).where(
                horse.c.sex.in_([HorseSexEnum.MALE.value, HorseSexEnum.GELD.value])
            )
            stmt = (
                delete(horse_children)
                .where(horse_children.c.child_id == target_horse_id)
                .where(horse_children.c.horse_id.in_(sire_parents))
            )
            await self.session.execute(stmt)
        if dam:
            dam_parents = select(horse.c.id).where(
                horse.c.sex == HorseSexEnum.FEMALE.value
            )
            stmt = (
                delete(horse_children)
                .where(horse_children.c.child_id == target_horse_id)
                .where(horse_children.c.horse_id.in_(dam_parents))
            )
            await self.session.execute(stmt)
        if foals is True:
            stmt = delete(horse_children).where(
                horse_children.c.horse_id == target_horse_id
            )
            await self.session.execute(stmt)
        elif isinstance(foals, list) and foals:
            stmt = (
                delete(horse_children)
                .where(horse_children.c.horse_id == target_horse_id)
                .where(horse_children.c.child_id.in_(foals))
            )
            await self.session.execute(stmt)
        await self.session.flush()

    async def set_pedigree(
        self,
        *,
        target_horse_id: UUID,
        sire_id: UUID | None = None,
        dam_id: UUID | None = None,
        foals_ids: list[UUID] | None = None,
    ) -> None:
        """Установить родословное древо лошади."""
        if sire_id is not None:
            await self.clear_pedigree(target_horse_id=target_horse_id, sire=True)
            stmt = insert(horse_children).values(
                horse_id=sire_id, child_id=target_horse_id
            )
            await self.session.execute(stmt)
        if dam_id is not None:
            await self.clear_pedigree(target_horse_id=target_horse_id, dam=True)
            stmt = insert(horse_children).values(
                horse_id=dam_id, child_id=target_horse_id
            )
            await self.session.execute(stmt)
        if foals_ids is not None:
            await self.clear_pedigree(target_horse_id=target_horse_id, foals=True)
            for foal_id in foals_ids:
                stmt = insert(horse_children).values(
                    horse_id=target_horse_id, child_id=foal_id
                )
                await self.session.execute(stmt)
        await self.session.flush()
