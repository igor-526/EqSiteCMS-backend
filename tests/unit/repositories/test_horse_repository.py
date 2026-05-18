from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql

from core.entities.horse import HorseKindEnum
from repositories.horse_repository import HorseRepository


class FakePhotoUrlBuilder:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def build(self, filename: str) -> str:
        self.calls.append(filename)
        return f"http://localhost:9000/gallery/{filename}"


class FakeExecuteResult:
    def mappings(self) -> "FakeExecuteResult":
        return self

    def all(self) -> list[dict]:
        return []

    def scalar(self) -> int:
        return 0

    def scalar_one_or_none(self) -> None:
        return None


class FakeAsyncSession:
    def __init__(self) -> None:
        self.statements: list[object] = []

    async def execute(self, statement: object) -> FakeExecuteResult:
        self.statements.append(statement)
        return FakeExecuteResult()


def compile_sql(statement: object) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


def test_horse_repository_builds_photo_urls_with_injected_builder() -> None:
    builder = FakePhotoUrlBuilder()
    repository = HorseRepository(
        session=object(),  # type: ignore[arg-type]
        photo_url_builder=builder,
    )

    dto = repository._build_horse_dto(
        horse_data={
            "id": UUID("11111111-1111-4111-8111-111111111111"),
            "slug": "winter-star",
            "name": "Winter Star",
            "sex": "female",
        },
        breed_data=None,
        coat_color_data=None,
        horse_owner_data=None,
        photos_data=[
            {
                "photo_id": UUID("22222222-2222-4222-8222-222222222222"),
                "is_main": True,
                "path": "horse.jpg",
            }
        ],
        services_data=[],
    )

    assert builder.calls == ["horse.jpg"]
    assert dto.photos[0].url == "http://localhost:9000/gallery/horse.jpg"
    assert "/media/" not in dto.photos[0].url
    assert "kind" not in dto.model_dump()


@pytest.mark.asyncio
async def test_horse_repository_kind_filter_uses_breed_kind_column() -> None:
    session = FakeAsyncSession()
    repository = HorseRepository(
        session=session,  # type: ignore[arg-type]
        photo_url_builder=FakePhotoUrlBuilder(),
    )

    await repository.get_horse_list_full_info(
        equestrian_id=UUID("11111111-1111-4111-8111-111111111111"),
        kind=[HorseKindEnum.PONY],
    )

    sql = compile_sql(session.statements[0])
    assert "breeds.kind IN ('pony')" in sql
    assert "horse.kind" not in sql


@pytest.mark.asyncio
async def test_horse_repository_kind_sort_uses_breed_kind_column() -> None:
    session = FakeAsyncSession()
    repository = HorseRepository(
        session=session,  # type: ignore[arg-type]
        photo_url_builder=FakePhotoUrlBuilder(),
    )

    await repository.get_horse_list_full_info(
        equestrian_id=UUID("11111111-1111-4111-8111-111111111111"),
        sort=["-kind"],
    )

    sql = compile_sql(session.statements[0])
    assert "ORDER BY breeds.kind DESC NULLS LAST" in sql
    assert "horse.kind" not in sql


@pytest.mark.asyncio
async def test_horse_repository_can_filter_candidates_without_breed() -> None:
    session = FakeAsyncSession()
    repository = HorseRepository(
        session=session,  # type: ignore[arg-type]
        photo_url_builder=FakePhotoUrlBuilder(),
    )

    await repository.get_horse_list_full_info(
        equestrian_id=UUID("11111111-1111-4111-8111-111111111111"),
        breed_id_is_null=True,
    )

    sql = compile_sql(session.statements[0])
    assert "horse.breed_id IS NULL" in sql
    assert "horse.kind" not in sql


def test_horse_repository_module_does_not_depend_on_backend_media_settings() -> None:
    import inspect

    import repositories.horse_repository as horse_repository_module

    source = inspect.getsource(horse_repository_module)

    assert "cms_backend_domain" not in source
    assert "/media/" not in source
