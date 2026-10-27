"""Расширяемый контракт таблиц; календарные правила принадлежат SEO."""

from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict


class MetricsMode(StrEnum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"


class MetricsMetric(StrEnum):
    VISITS = "visits"
    USERS = "users"
    PAGEVIEWS = "pageviews"
    BOUNCES = "bounces"
    BOUNCE_RATE = "bounce_rate"
    PAGE_DEPTH = "page_depth"
    AVG_VISIT_DURATION_SECONDS = "avg_visit_duration_seconds"
    VISIT_DURATION_SECONDS = "visit_duration_seconds"


class ExtensibleMetricsDto(BaseModel):
    model_config = ConfigDict(extra="allow")


class MetricsPeriodOutDto(ExtensibleMetricsDto):
    mode: str
    date_from: date
    date_to: date
    requested_date_from: date | None
    requested_date_to: date | None
    defaulted: bool
    adjusted: bool
    clamped: bool
    today: date


class MetricsMetricOutDto(ExtensibleMetricsDto):
    key: str
    title: str
    value_type: str


class MetricsCellOutDto(ExtensibleMetricsDto):
    text: str
    value: int | float | None
    hint: str | None = None


class MetricsColumnOutDto(ExtensibleMetricsDto):
    key: str
    title: str
    hint: str | None
    sortable: bool
    value_type: str
    align: Literal["left", "right"]
    empty_text: str
    values: dict[str, MetricsCellOutDto]


class MetricsTableOutDto(ExtensibleMetricsDto):
    version: int
    row_key: str
    period: MetricsPeriodOutDto
    metric: MetricsMetricOutDto
    ordering: str | None
    columns: list[MetricsColumnOutDto]
