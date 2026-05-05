import json
from datetime import datetime
from typing import Literal
from uuid import UUID

from core.entities.site_settings import SiteSetting, SiteSettingType
from core.exceptions.base import ClientError
from core.protocols.repositories.site_settings_repository import (
    SiteSettingsRepositoryProtocol,
)
from core.schemas.site_settings import SiteSettingCreateDto, SiteSettingUpdateDto


class SiteSettingsService:
    def __init__(self, site_settings_repository: SiteSettingsRepositoryProtocol):
        self.site_settings_repository = site_settings_repository

    def _validate_value_by_type(self, value: str, setting_type: SiteSettingType) -> str:
        """Валидирует значение в зависимости от типа и возвращает строковое представление."""
        try:
            if setting_type == SiteSettingType.string:
                # Любая строка - просто возвращаем
                return value

            elif setting_type == SiteSettingType.number:
                # Целое число
                int(value)
                return value

            elif setting_type == SiteSettingType.float:
                # Число с плавающей точкой
                float(value)
                return value

            elif setting_type == SiteSettingType.boolean:
                # Булево значение
                value_lower = value.lower().strip()
                if value_lower not in (
                    "true",
                    "false",
                    "1",
                    "0",
                    "yes",
                    "no",
                    "on",
                    "off",
                ):
                    raise ValueError(f"Неверное булево значение: {value}")
                # Нормализуем к true/false
                normalized = value_lower in ("true", "1", "yes", "on")
                return "true" if normalized else "false"

            elif setting_type == SiteSettingType.object:
                # Валидный JSON
                json.loads(value)
                return value

            elif setting_type == SiteSettingType.date:
                # Дата в формате YYYY-MM-DD
                from datetime import date as date_type

                date_type.fromisoformat(value)
                return value

            elif setting_type == SiteSettingType.time:
                # Время в формате HH:MM
                datetime.strptime(value, "%H:%M")
                return value

            elif setting_type == SiteSettingType.datetime:
                # Дата и время в формате "YYYY-MM-DD HH:MM"
                datetime.strptime(value, "%Y-%m-%d %H:%M")
                return value

            else:
                raise ClientError(f"Неизвестный тип настройки: {setting_type}")

        except ValueError as e:
            raise ClientError(f"Неверное значение для типа {setting_type}: {str(e)}")
        except json.JSONDecodeError:
            raise ClientError(f"Неверный JSON для типа object: {value}")

    async def create(self, data: SiteSettingCreateDto) -> SiteSetting:
        """Создать новую настройку."""
        # Проверяем уникальность key
        existing_by_key = await self.site_settings_repository.find_by_key(data.key)
        if existing_by_key is not None:
            raise ClientError(f"Настройка с ключом '{data.key}' уже существует")

        # Проверяем уникальность name
        existing_by_name = await self.site_settings_repository.find_by_name(data.name)
        if existing_by_name is not None:
            raise ClientError(f"Настройка с названием '{data.name}' уже существует")

        # Валидируем значение по типу
        validated_value = self._validate_value_by_type(data.value, data.type)

        site_setting = SiteSetting(
            key=data.key,
            value=validated_value,
            name=data.name,
            description=data.description,
            type=str(data.type),
        )

        return await self.site_settings_repository.create(site_setting)

    async def update(self, id: UUID, data: SiteSettingUpdateDto) -> SiteSetting:
        """Обновить настройку."""
        site_setting = await self.site_settings_repository.get_by_id(id)
        if site_setting is None:
            raise ClientError("Настройка не найдена")

        update_data = data.model_dump(exclude_none=True)

        # Если обновляется key, проверяем уникальность
        if "key" in update_data:
            existing = await self.site_settings_repository.find_by_key(
                update_data["key"]
            )
            if existing is not None and existing.id != site_setting.id:
                raise ClientError(
                    f"Настройка с ключом '{update_data['key']}' уже существует"
                )

        # Если обновляется name, проверяем уникальность
        if "name" in update_data:
            existing = await self.site_settings_repository.find_by_name(
                update_data["name"]
            )
            if existing is not None and existing.id != site_setting.id:
                raise ClientError(
                    f"Настройка с названием '{update_data['name']}' уже существует"
                )

        # Если обновляется value или type, валидируем значение
        if "value" in update_data or "type" in update_data:
            value = update_data.get("value", site_setting.value)
            setting_type = SiteSettingType(update_data.get("type", site_setting.type))
            validated_value = self._validate_value_by_type(value, setting_type)
            update_data["value"] = validated_value

        # Если обновляется type, преобразуем в строку
        if "type" in update_data:
            update_data["type"] = str(update_data["type"])

        for key, value in update_data.items():
            setattr(site_setting, key, value)

        return await self.site_settings_repository.update(site_setting)

    async def get_by_id(self, id: UUID) -> SiteSetting | None:
        """Получить настройку по UUID."""
        return await self.site_settings_repository.get_by_id(id)

    async def delete(self, id: UUID) -> None:
        """Удалить настройку."""
        site_setting = await self.site_settings_repository.get_by_id(id)
        if site_setting is None:
            raise ClientError("Настройка не найдена")
        await self.site_settings_repository.delete(id)

    async def get_filtered(
        self,
        *,
        key: list[str] | None = None,
        name: str | None = None,
        value: str | None = None,
        description: str | None = None,
        type: (
            list[
                Literal[
                    "string",
                    "number",
                    "float",
                    "boolean",
                    "object",
                    "date",
                    "time",
                    "datetime",
                ]
            ]
            | None
        ) = None,
        sort: (
            list[Literal["key", "name", "type", "-key", "-name", "-type"]] | None
        ) = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> tuple[list[SiteSetting], int]:
        """Получить отфильтрованный список настроек."""
        return await self.site_settings_repository.get_filtered(
            key=key,
            name=name,
            value=value,
            description=description,
            type=type,
            sort=sort,
            limit=limit,
            offset=offset,
        )
