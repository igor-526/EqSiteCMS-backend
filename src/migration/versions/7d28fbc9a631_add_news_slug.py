"""Persist tenant-unique news slugs, including scheduled and deleted rows.

The generator is frozen here: do not import the runtime slug implementation.
Upgrade holds the ALTER TABLE lock until the transaction finishes; schedule it
against the actual news volume. Downgrade removes slugs only, preserving news.
"""

import re
from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa
from alembic import op

revision: str = "7d28fbc9a631"
down_revision: str | None = "c055bacc0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _generate_slug(text: str, news_id: UUID) -> str:
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

    result = re.sub(r"[^a-z0-9-]", "", result)
    result = re.sub(r"-+", "-", result).strip("-")
    base = result[:127].rstrip("-") or "news"
    return f"{base}-{news_id.hex}"


def upgrade() -> None:
    op.add_column("news", sa.Column("slug", sa.String(160), nullable=True))
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, name FROM news")).mappings()
    for row in rows:
        connection.execute(
            sa.text("UPDATE news SET slug = :slug WHERE id = :id"),
            {"id": row["id"], "slug": _generate_slug(row["name"], row["id"])},
        )
    op.alter_column("news", "slug", existing_type=sa.String(160), nullable=False)
    op.create_unique_constraint(
        "uq_news_equestrian_slug", "news", ["equestrian_id", "slug"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_news_equestrian_slug", "news", type_="unique")
    op.drop_column("news", "slug")
