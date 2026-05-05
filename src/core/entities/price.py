from enum import StrEnum, auto


class PriceFormatter(StrEnum):
    """Формат отображения цены."""

    equal = auto()
    gt = auto()
    lt = auto()
    discuss = auto()
