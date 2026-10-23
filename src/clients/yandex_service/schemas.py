from uuid import UUID

from pydantic import BaseModel, Field


class YandexAccountOutDto(BaseModel):
    id: UUID
    yandex_id: str
    yandex_login: str
    display_name: str
    email: str | None = None
    yandex_phone: str | None = None


class YandexAccountsOutDto(BaseModel):
    items: list[YandexAccountOutDto]
    total: int = Field(ge=0)


class YandexAuthLinkOutDto(BaseModel):
    auth_link: str


class YandexMetricaCounterOutDto(BaseModel):
    counter_id: int
    site: str


class YandexMetricaCountersOutDto(BaseModel):
    items: list[YandexMetricaCounterOutDto]
    total: int = Field(ge=0)


class YandexMetricaConnectionOutDto(BaseModel):
    id: UUID
    counter_id: str
    yandex_account: YandexAccountOutDto


class YandexMetricaConnectedCounterOutDto(BaseModel):
    counter: YandexMetricaConnectionOutDto | None


class YandexAuthCodeInDto(BaseModel):
    code: str
    state: str


class YandexMetricaSetConnectionInDto(BaseModel):
    yandex_account_id: UUID
    counter_id: str = Field(coerce_numbers_to_str=True)
