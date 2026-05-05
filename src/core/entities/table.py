from enum import StrEnum, auto

from pydantic import BaseModel, Field


class TableCellFormatter(StrEnum):
    """Форматтер для отображения значения в ячейке."""

    text_bold = auto()
    text_italic = auto()
    text_underline = auto()


class TableColumn(BaseModel):
    """Колонка таблицы."""

    key: str = Field(
        default=...,
        description="Ключ колонки",
    )
    title: str = Field(
        default=...,
        description="Отображаемое наименование колонки",
    )
    annotation: str = Field(
        default=...,
        description="Аннотация при наведении",
    )
    cell_formatter: list[TableCellFormatter] = Field(
        default=[],
        description="Форматтер для отображения значения в ячейке",
    )


class TableCell(BaseModel):
    """Ячейка таблицы."""

    value: str = Field(
        default="",
        examples=["1000"],
        description="Значение ячейки",
    )
    annotation: str = Field(
        default="",
        description="Аннотация при наведении",
    )
    cell_formatter: list[TableCellFormatter] = Field(
        default=[],
        description="Форматтер для отображения значения в ячейке",
    )


class TableRow(BaseModel):
    """Строка таблицы."""

    cells: dict[str, TableCell] = Field(
        default={},
        description="Ячейки строки по ключам колонок",
    )


class Table(BaseModel):
    """Таблица."""

    columns: list[TableColumn] = Field(
        default=[],
        description="Колонки таблицы",
    )
    rows: list[TableRow] = Field(
        default=[],
        description="Строки таблицы",
    )
