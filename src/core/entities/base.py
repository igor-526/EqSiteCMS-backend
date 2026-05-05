import re
from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _generate_slug(text: str) -> str:
    """Генерирует slug из текста."""
    # Таблица транслитерации русских символов
    translit_map = {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "yo",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "y",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "h",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "sch",
        "ъ": "",
        "ы": "y",
        "ь": "",
        "э": "e",
        "ю": "yu",
        "я": "ya",
        "А": "A",
        "Б": "B",
        "В": "V",
        "Г": "G",
        "Д": "D",
        "Е": "E",
        "Ё": "Yo",
        "Ж": "Zh",
        "З": "Z",
        "И": "I",
        "Й": "Y",
        "К": "K",
        "Л": "L",
        "М": "M",
        "Н": "N",
        "О": "O",
        "П": "P",
        "Р": "R",
        "С": "S",
        "Т": "T",
        "У": "U",
        "Ф": "F",
        "Х": "H",
        "Ц": "Ts",
        "Ч": "Ch",
        "Ш": "Sh",
        "Щ": "Sch",
        "Ъ": "",
        "Ы": "Y",
        "Ь": "",
        "Э": "E",
        "Ю": "Yu",
        "Я": "Ya",
    }

    # Транслитерация
    result = ""
    for char in text:
        result += translit_map.get(char, char)

    # Приведение к нижнему регистру
    result = result.lower()

    # Замена пробелов и спецсимволов на дефисы
    result = re.sub(r"[^\w\s-]", "", result)
    result = re.sub(r"[-\s]+", "-", result)

    # Удаление дефисов в начале и конце
    result = result.strip("-")

    return result


class TimeStampMixin(BaseModel):
    """Миксин с временными метками создания и обновления."""

    created_at: datetime = Field(
        default_factory=datetime.now,
        description="Момент создания сущности",
    )
    updated_at: datetime | None = Field(
        default_factory=datetime.now,
        description="Момент последнего обновления",
    )


class SlugMixin(BaseModel):
    """Миксин с автоматической генерацией slug из name."""

    slug: str | None = Field(
        default=None,
        description="Уникальный идентификатор для URL (автоматически генерируется из name, если не задан)",
        examples=["example-slug"],
    )

    @model_validator(mode="after")
    def _generate_slug_from_name(self) -> "SlugMixin":
        """Генерирует slug из name, если slug не задан явно."""
        if hasattr(self, "name") and (self.slug is None or self.slug == ""):
            name_value = getattr(self, "name", None)
            if name_value and str(name_value).strip():
                self.slug = _generate_slug(str(name_value).strip())
        return self


class Entity(BaseModel):
    """Базовая сущность с уникальным идентификатором."""

    id: UUID = Field(
        default_factory=uuid4,
        description="Уникальный идентификатор сущности",
    )
    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def _check_invariants(self) -> "Entity":
        return self


class PaginatedEntities[T](BaseModel):
    """Пагинированный список сущностей или DTO."""

    items: list[T] = Field(
        default_factory=list,
        description="Список элементов",
    )
    total: int = Field(
        default=0,
        description="Общее количество элементов",
    )
