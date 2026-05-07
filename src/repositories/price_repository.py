from typing import Literal
from uuid import UUID

from sqlalchemy import Table, and_, delete, func, insert, or_, select, update

from core.entities.prices import Price, PriceGroup, PriceGroupsRelation, PricePhotos
from models.prices import price_groups, price_groups_relations, price_photos, prices

from .abstract_repository import TenantScopedRepository


class PriceGroupRepository(TenantScopedRepository[PriceGroup]):
    table: Table = price_groups
    entity = PriceGroup

    async def find_by_name(
        self, name: str, *, equestrian_id: UUID
    ) -> PriceGroup | None:
        """Проверить существование name."""
        stmt = select(self.table).where(
            self.table.c.name == name,
            self.table.c.equestrian_id == equestrian_id,
        )
        row = await self.session.execute(stmt)
        mapping = row.mappings().first()
        if mapping is None:
            return None
        return self.entity.model_validate(dict(mapping))

    async def get_filtered(
        self,
        *,
        equestrian_id: UUID,
        name: str | None = None,
        description: str | None = None,
        sort: list[Literal["name", "-name"]] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[PriceGroup], int]:
        """Получить отфильтрованный список с подсчётом общего количества."""
        stmt = select(self.table).where(self.table.c.equestrian_id == equestrian_id)
        count_stmt = (
            select(func.count())
            .select_from(self.table)
            .where(self.table.c.equestrian_id == equestrian_id)
        )

        conditions = []
        if name:
            conditions.append(self.table.c.name.ilike(f"%{name}%"))
        if description:
            conditions.append(self.table.c.description.ilike(f"%{description}%"))

        if conditions:
            where_clause = or_(*conditions)
            stmt = stmt.where(where_clause)
            count_stmt = count_stmt.where(where_clause)

        # Сортировка
        if sort:
            order_by_clauses = []
            for field in sort:
                if field.startswith("-"):
                    order_by_clauses.append(self.table.c[field[1:]].desc())
                else:
                    order_by_clauses.append(self.table.c[field].asc())
            stmt = stmt.order_by(*order_by_clauses)

        # Пагинация
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)

        rows = await self.session.execute(stmt)
        entities = [
            self.entity.model_validate(dict(row)) for row in rows.mappings().all()
        ]

        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        return entities, total


class PriceRepository(TenantScopedRepository[Price]):
    table: Table = prices
    entity = Price

    async def find_by_name(self, name: str, *, equestrian_id: UUID) -> Price | None:
        """Проверить существование name."""
        stmt = select(self.table).where(
            self.table.c.name == name,
            self.table.c.equestrian_id == equestrian_id,
        )
        row = await self.session.execute(stmt)
        mapping = row.mappings().first()
        if mapping is None:
            return None
        return self.entity.model_validate(dict(mapping))

    def _parse_slug_or_id(self, slug_or_id: str) -> str | UUID:
        """Попытаться преобразовать строку в UUID, иначе вернуть как есть."""
        try:
            return UUID(slug_or_id)
        except ValueError:
            return slug_or_id

    async def get_by_slug_or_id(
        self, slug_or_id: str | UUID, *, equestrian_id: UUID
    ) -> Price | None:
        """Получить цену по slug или UUID."""
        if isinstance(slug_or_id, UUID):
            return await self.get_by_id(slug_or_id, equestrian_id=equestrian_id)

        parsed = self._parse_slug_or_id(slug_or_id)
        if isinstance(parsed, UUID):
            return await self.get_by_id(parsed, equestrian_id=equestrian_id)
        stmt = select(self.table).where(
            self.table.c.slug == parsed,
            self.table.c.equestrian_id == equestrian_id,
        )
        row = await self.session.execute(stmt)
        mapping = row.mappings().first()
        if mapping is None:
            return None
        return self.entity.model_validate(dict(mapping))

    async def get_filtered(
        self,
        *,
        equestrian_id: UUID,
        name: str | list[str] | None = None,
        description: str | None = None,
        groups: str | list[str] | None = None,
        sort: list[Literal["name", "-name"]] | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[Price], int]:
        """Получить отфильтрованный список с подсчётом общего количества."""
        stmt = select(self.table).where(self.table.c.equestrian_id == equestrian_id)
        count_stmt = (
            select(func.count())
            .select_from(self.table)
            .where(self.table.c.equestrian_id == equestrian_id)
        )

        conditions = []

        # Фильтр по name - вхождение или список вхождений
        if name:
            if isinstance(name, list):
                name_conditions = [self.table.c.name.ilike(f"%{n}%") for n in name]
                conditions.append(or_(*name_conditions))
            else:
                conditions.append(self.table.c.name.ilike(f"%{name}%"))

        # Фильтр по description - вхождение
        if description:
            conditions.append(self.table.c.description.ilike(f"%{description}%"))

        # Фильтр по groups - полное совпадение с наименованием группы
        if groups:
            if isinstance(groups, str):
                groups = [groups]

            # Подзапрос для получения price_id через группы
            group_ids_subquery = select(price_groups.c.id).where(
                or_(*[price_groups.c.name == g for g in groups]),
                price_groups.c.equestrian_id == equestrian_id,
            )

            price_ids_subquery = (
                select(price_groups_relations.c.price_id)
                .where(price_groups_relations.c.group_id.in_(group_ids_subquery))
                .distinct()
            )

            conditions.append(self.table.c.id.in_(price_ids_subquery))

        if conditions:
            where_clause = and_(*conditions)
            stmt = stmt.where(where_clause)
            count_stmt = count_stmt.where(where_clause)

        # Сортировка
        if sort:
            order_by_clauses = []
            for field in sort:
                if field.startswith("-"):
                    order_by_clauses.append(self.table.c[field[1:]].desc())
                else:
                    order_by_clauses.append(self.table.c[field].asc())
            stmt = stmt.order_by(*order_by_clauses)
        elif groups:
            # Дефолтная сортировка по display_order при groups-фильтре
            group_ids_for_sort = select(price_groups.c.id).where(
                or_(
                    *[
                        price_groups.c.name == g
                        for g in (groups if isinstance(groups, list) else [groups])
                    ]
                ),
                price_groups.c.equestrian_id == equestrian_id,
            )
            min_order_subq = (
                select(
                    price_groups_relations.c.price_id,
                    func.min(price_groups_relations.c.display_order).label("min_order"),
                )
                .where(price_groups_relations.c.group_id.in_(group_ids_for_sort))
                .group_by(price_groups_relations.c.price_id)
                .subquery()
            )
            stmt = stmt.outerjoin(
                min_order_subq, self.table.c.id == min_order_subq.c.price_id
            )
            stmt = stmt.order_by(min_order_subq.c.min_order.asc().nullslast())
        else:
            stmt = stmt.order_by(self.table.c.created_at.desc())

        # Пагинация
        if limit is not None:
            stmt = stmt.limit(limit)
        if offset is not None:
            stmt = stmt.offset(offset)

        rows = await self.session.execute(stmt)
        entities = [
            self.entity.model_validate(dict(row)) for row in rows.mappings().all()
        ]

        total_result = await self.session.execute(count_stmt)
        total = total_result.scalar() or 0

        return entities, total

    async def get_price_groups(
        self, price_id: UUID, *, equestrian_id: UUID
    ) -> list[PriceGroupsRelation]:
        """Получить связи цены с группами."""
        stmt = (
            select(price_groups_relations)
            .join(prices, price_groups_relations.c.price_id == prices.c.id)
            .where(
                price_groups_relations.c.price_id == price_id,
                prices.c.equestrian_id == equestrian_id,
            )
        )
        rows = await self.session.execute(stmt)
        return [
            PriceGroupsRelation.model_validate(dict(row))
            for row in rows.mappings().all()
        ]

    async def set_price_groups(
        self, price_id: UUID, group_ids: list[UUID], *, equestrian_id: UUID
    ) -> None:
        """Установить связи цены с группами (заменяет все существующие)."""
        # Удаляем все существующие связи
        delete_stmt = delete(price_groups_relations).where(
            price_groups_relations.c.price_id == price_id,
            price_groups_relations.c.price_id.in_(
                select(prices.c.id).where(prices.c.equestrian_id == equestrian_id)
            ),
        )
        await self.session.execute(delete_stmt)

        # Добавляем новые связи с назначением display_order = MAX + 1
        for group_id in group_ids:
            max_stmt = select(func.max(price_groups_relations.c.display_order)).where(
                price_groups_relations.c.group_id == group_id
            )
            max_result = await self.session.execute(max_stmt)
            current_max = max_result.scalar() or 0
            values = {
                "price_id": price_id,
                "group_id": group_id,
                "display_order": current_max + 1,
            }
            await self.session.execute(insert(price_groups_relations).values(values))

        await self.session.flush()

    async def get_price_photos(
        self, price_id: UUID, *, equestrian_id: UUID
    ) -> list[PricePhotos]:
        """Получить связи цены с фотографиями."""
        stmt = (
            select(price_photos)
            .join(prices, price_photos.c.price_id == prices.c.id)
            .where(
                price_photos.c.price_id == price_id,
                prices.c.equestrian_id == equestrian_id,
            )
        )
        rows = await self.session.execute(stmt)
        return [PricePhotos.model_validate(dict(row)) for row in rows.mappings().all()]

    async def set_price_photos(
        self,
        price_id: UUID,
        photo_ids: list[UUID] | None = None,
        main_photo_id: UUID | None = None,
        *,
        equestrian_id: UUID,
    ) -> None:
        """Установить связи цены с фотографиями."""
        # Если передан photo_ids, заменяем все связи
        if photo_ids is not None:
            # Удаляем все существующие связи
            delete_stmt = delete(price_photos).where(
                price_photos.c.price_id == price_id,
                price_photos.c.price_id.in_(
                    select(prices.c.id).where(prices.c.equestrian_id == equestrian_id)
                ),
            )
            await self.session.execute(delete_stmt)

            # Добавляем новые связи
            if photo_ids:
                values = [
                    {"price_id": price_id, "photo_id": photo_id, "is_main": False}
                    for photo_id in photo_ids
                ]
                insert_stmt = insert(price_photos).values(values)
                await self.session.execute(insert_stmt)

        # Устанавливаем главную фотографию
        if main_photo_id is not None:
            # Сбрасываем все is_main на False для этой цены
            update_all_stmt = (
                update(price_photos)
                .where(
                    price_photos.c.price_id == price_id,
                    price_photos.c.price_id.in_(
                        select(prices.c.id).where(
                            prices.c.equestrian_id == equestrian_id
                        )
                    ),
                )
                .values(is_main=False)
            )
            await self.session.execute(update_all_stmt)

            # Устанавливаем is_main=True для указанной фотографии
            # Сначала проверяем, существует ли связь
            check_stmt = select(price_photos).where(
                and_(
                    price_photos.c.price_id == price_id,
                    price_photos.c.photo_id == main_photo_id,
                )
            )
            check_result = await self.session.execute(check_stmt)
            if check_result.mappings().first():
                # Связь существует, обновляем
                update_main_stmt = (
                    update(price_photos)
                    .where(
                        and_(
                            price_photos.c.price_id == price_id,
                            price_photos.c.photo_id == main_photo_id,
                        )
                    )
                    .values(is_main=True)
                )
                await self.session.execute(update_main_stmt)
            else:
                # Связи нет, создаем новую
                insert_main_stmt = insert(price_photos).values(
                    price_id=price_id, photo_id=main_photo_id, is_main=True
                )
                await self.session.execute(insert_main_stmt)

        await self.session.flush()

    async def get_group_relations_ordered(
        self, group_id: UUID, *, equestrian_id: UUID
    ) -> list[PriceGroupsRelation]:
        """Получить связи группы, упорядоченные по display_order."""
        stmt = (
            select(price_groups_relations)
            .join(price_groups, price_groups_relations.c.group_id == price_groups.c.id)
            .where(
                price_groups_relations.c.group_id == group_id,
                price_groups.c.equestrian_id == equestrian_id,
            )
            .order_by(price_groups_relations.c.display_order.asc().nullslast())
        )
        rows = await self.session.execute(stmt)
        return [
            PriceGroupsRelation.model_validate(dict(row))
            for row in rows.mappings().all()
        ]

    async def set_display_orders(
        self, group_id: UUID, order_map: dict[UUID, int], *, equestrian_id: UUID
    ) -> None:
        """Двухфазное обновление display_order для избегания UniqueViolation."""
        # Сначала проверяем что group_id принадлежит нужному equestrian
        group_check = select(price_groups).where(
            price_groups.c.id == group_id,
            price_groups.c.equestrian_id == equestrian_id,
        )
        if not (await self.session.execute(group_check)).mappings().first():
            return

        # Фаза 1: сбрасываем display_order в NULL для всех строк группы
        await self.session.execute(
            update(price_groups_relations)
            .where(price_groups_relations.c.group_id == group_id)
            .values(display_order=None)
        )
        await self.session.flush()

        # Фаза 2: выставляем финальные значения
        for price_id, order in order_map.items():
            await self.session.execute(
                update(price_groups_relations)
                .where(
                    price_groups_relations.c.price_id == price_id,
                    price_groups_relations.c.group_id == group_id,
                )
                .values(display_order=order)
            )
        await self.session.flush()
