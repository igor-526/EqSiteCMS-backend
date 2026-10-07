"""Unit tests for HorseService.upload_and_attach_photos (BE-4)."""

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from core.entities.equestrian import EquestrianContext
from core.entities.horse import Horse
from core.exceptions.base import ClientError
from core.schemas.horses import HorsePhotosUploadDto
from core.schemas.photos import (
    PhotoBatchUploadResponseDto,
    PhotoOutShortDto,
)
from core.services.horse import HorseService
from tests.unit.conftest import (
    TEST_ADMIN_USER,
    TEST_EQUESTRIAN_CONTEXT,
    TEST_EQUESTRIAN_ID,
)


class FakeHorseRepository:
    """Fake horse repository для изоляции unit tests."""

    def __init__(self) -> None:
        self.horses: dict[UUID, Horse] = {}
        self.photo_relations: dict[UUID, list[MagicMock]] = {}

    async def get_by_id(self, horse_id: UUID, *, equestrian_id: UUID) -> Horse | None:
        """Получить horse по id."""
        horse = self.horses.get(horse_id)
        if horse and horse.equestrian_id == equestrian_id:
            return horse
        return None

    async def get_horse_photos(
        self, horse_id: UUID, *, equestrian_id: UUID
    ) -> list[MagicMock]:
        """Получить связи horse-photo."""
        return self.photo_relations.get(horse_id, [])

    async def get_horse_full_info_by_id(
        self, *, horse_id: UUID, equestrian_id: UUID, pedigree: int | None = None
    ) -> MagicMock | None:
        """Получить полную информацию о лошади с фотографиями."""
        from core.schemas.photos import PhotoOutShortDto

        horse = self.horses.get(horse_id)
        if not horse or horse.equestrian_id != equestrian_id:
            return None

        # Создаём mock HorseOutDto с photos
        horse_info = MagicMock()
        horse_info.id = horse.id
        horse_info.name = horse.name
        horse_info.slug = horse.slug
        horse_info.equestrian_id = horse.equestrian_id

        # Получаем текущие фото из photo_relations
        photo_relations = self.photo_relations.get(horse_id, [])
        photos = []
        for rel in photo_relations:
            photo = PhotoOutShortDto(
                id=rel.photo_id,
                name=f"photo_{rel.photo_id}",
                url=f"http://example.com/photos/{rel.photo_id}.jpg",
                thumbnail_url=f"http://example.com/photos/{rel.photo_id}_thumb.jpg",
                is_main=rel.is_main,
            )
            photos.append(photo)
        horse_info.photos = photos

        return horse_info

    async def set_horse_photos(
        self,
        horse_id: UUID,
        photo_ids: list[UUID],
        *,
        main_photo_id: UUID | None = None,
        equestrian_id: UUID,
    ) -> None:
        """Установить список фото для horse."""
        self.photo_relations[horse_id] = []
        for photo_id in photo_ids:
            relation = MagicMock()
            relation.photo_id = photo_id
            relation.is_main = photo_id == main_photo_id
            self.photo_relations[horse_id].append(relation)


@pytest.fixture
def fake_horse_repository() -> FakeHorseRepository:
    """Создать fake horse repository."""
    return FakeHorseRepository()


@pytest.fixture
def mock_photo_service() -> AsyncMock:
    """Создать mock PhotoService."""
    from datetime import datetime, timezone

    from core.entities.photos import Photo

    service = AsyncMock()

    # Default mock для create: возвращает Photo entity с path
    async def create_photo(data, upload, *, equestrian_context: EquestrianContext):
        photo_id = uuid4()
        return Photo(
            id=photo_id,
            name=data.name or upload.filename,
            description=data.description,
            path=f"photos/{photo_id}.jpg",
            equestrian_id=equestrian_context.id,
            created_at=datetime.now(timezone.utc),
        )

    service.create.side_effect = create_photo
    return service


@pytest.fixture
def horse_service(
    fake_horse_repository: FakeHorseRepository,
    mock_photo_service: AsyncMock,
) -> HorseService:
    """Создать HorseService с fake dependencies."""
    # Mock photo_url_builder to return proper URLs
    photo_url_builder = MagicMock()
    photo_url_builder.build.side_effect = lambda path: f"https://example.com/{path}"

    service = HorseService(
        horse_repository=cast(Any, fake_horse_repository),
        horse_children_repository=MagicMock(),
        breed_repository=MagicMock(),
        coat_color_repository=MagicMock(),
        horse_owner_repository=MagicMock(),
        photo_repository=MagicMock(),
        photo_url_builder=photo_url_builder,
        photo_service=mock_photo_service,
    )
    return service


@pytest.fixture
def test_horse(fake_horse_repository: FakeHorseRepository) -> Horse:
    """Создать тестовую лошадь."""
    horse = Horse(
        id=uuid4(),
        name="Test Horse",
        slug="test-horse",
        equestrian_id=TEST_EQUESTRIAN_ID,
    )
    fake_horse_repository.horses[horse.id] = horse
    return horse


@pytest.mark.asyncio
async def test_upload_and_attach_photos_success(
    horse_service: HorseService,
    test_horse: Horse,
    mock_photo_service: AsyncMock,
) -> None:
    """Тест успешной загрузки 5 файлов к лошади."""
    # Arrange
    files = [b"image1", b"image2", b"image3", b"image4", b"image5"]
    filenames = [f"photo{i}.jpg" for i in range(1, 6)]
    dto = HorsePhotosUploadDto(files=files)

    # Act
    result = await horse_service.upload_and_attach_photos(
        test_horse.id,
        dto,
        filenames,
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        user=TEST_ADMIN_USER,
    )

    # Assert
    assert isinstance(result, PhotoBatchUploadResponseDto)
    assert len(result.photos) == 5
    assert result.errors is None or len(result.errors) == 0

    # Проверяем что PhotoService.create вызван 5 раз
    assert mock_photo_service.create.call_count == 5

    # Проверяем что все фото успешно созданы
    for photo in result.photos:
        assert isinstance(photo, PhotoOutShortDto)
        assert photo.url.startswith("https://")


@pytest.mark.asyncio
async def test_upload_and_attach_photos_partial_success(
    horse_service: HorseService,
    test_horse: Horse,
) -> None:
    """Тест partial success для лошади."""
    from datetime import datetime, timezone

    from core.entities.photos import Photo

    # Arrange
    files = [b"image1", b"image2", b"image3"]
    filenames = ["photo1.jpg", "photo2.jpg", "photo3.jpg"]
    dto = HorsePhotosUploadDto(files=files)

    # Mock PhotoService.create: третий файл вызывает ошибку
    call_count = 0

    async def create_with_error(data, upload, *, equestrian_context):
        nonlocal call_count
        call_count += 1
        if call_count == 3:
            raise ClientError("Invalid image format")

        photo_id = uuid4()
        return Photo(
            id=photo_id,
            name=data.name or upload.filename,
            description=data.description,
            path=f"photos/{photo_id}.jpg",
            equestrian_id=equestrian_context.id,
            created_at=datetime.now(timezone.utc),
        )

    assert horse_service.photo_service is not None
    cast(AsyncMock, horse_service.photo_service.create).side_effect = create_with_error

    # Act
    result = await horse_service.upload_and_attach_photos(
        test_horse.id,
        dto,
        filenames,
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        user=TEST_ADMIN_USER,
    )

    # Assert
    assert len(result.photos) == 2  # Только 2 успешных
    assert result.errors is not None
    assert len(result.errors) == 1
    assert result.errors[0].index == 2  # Третий файл (index 2)


@pytest.mark.asyncio
async def test_upload_and_attach_photos_horse_not_found(
    horse_service: HorseService,
    mock_photo_service: AsyncMock,
) -> None:
    """Тест ошибки: несуществующая лошадь (404)."""
    # Arrange
    non_existent_id = uuid4()
    files = [b"image1"]
    filenames = ["photo1.jpg"]
    dto = HorsePhotosUploadDto(files=files)

    # Act & Assert
    with pytest.raises(ClientError, match="Лошадь не найдена"):
        await horse_service.upload_and_attach_photos(
            non_existent_id,
            dto,
            filenames,
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
            user=TEST_ADMIN_USER,
        )

    # Проверяем что PhotoService.create не вызывался
    mock_photo_service.create.assert_not_called()


@pytest.mark.asyncio
async def test_upload_and_attach_photos_without_admin_permission(
    horse_service: HorseService,
    test_horse: Horse,
    mock_photo_service: AsyncMock,
) -> None:
    """Тест попытки загрузить без admin прав (403)."""
    # Arrange
    from datetime import datetime, timezone

    from core.schemas.users import UserOutDto

    non_admin_user = UserOutDto(
        id=uuid4(),
        equestrian_id=TEST_EQUESTRIAN_ID,
        username="non-admin",
        created_at=datetime.now(timezone.utc),
        scopes=[],  # Нет admin scope
    )

    files = [b"image1"]
    filenames = ["photo1.jpg"]
    dto = HorsePhotosUploadDto(files=files)

    # Act & Assert
    from core.exceptions.auth import ForbiddenError

    with pytest.raises(ForbiddenError, match="Недостаточно прав"):
        await horse_service.upload_and_attach_photos(
            test_horse.id,
            dto,
            filenames,
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
            user=non_admin_user,
        )

    # Проверяем что PhotoService.create не вызывался
    mock_photo_service.create.assert_not_called()


@pytest.mark.asyncio
async def test_upload_and_attach_photos_wrong_tenant(
    horse_service: HorseService,
    fake_horse_repository: FakeHorseRepository,
    mock_photo_service: AsyncMock,
) -> None:
    """Тест попытки загрузить к лошади другого tenant (403)."""
    # Arrange
    other_tenant_id = uuid4()
    other_horse = Horse(
        id=uuid4(),
        name="Other Horse",
        slug="other-horse",
        equestrian_id=other_tenant_id,
    )
    fake_horse_repository.horses[other_horse.id] = other_horse

    files = [b"image1"]
    filenames = ["photo1.jpg"]
    dto = HorsePhotosUploadDto(files=files)

    # Act & Assert - попытка доступа с другим equestrian_context
    with pytest.raises(ClientError, match="Лошадь не найдена"):
        await horse_service.upload_and_attach_photos(
            other_horse.id,
            dto,
            filenames,
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
            user=TEST_ADMIN_USER,
        )

    # Проверяем что PhotoService.create не вызывался
    mock_photo_service.create.assert_not_called()


@pytest.mark.asyncio
async def test_upload_and_attach_photos_with_metadata(
    horse_service: HorseService,
    test_horse: Horse,
    mock_photo_service: AsyncMock,
) -> None:
    """Тест загрузки с метаданными для лошади."""
    # Arrange
    files = [b"image1", b"image2"]
    filenames = ["photo1.jpg", "photo2.jpg"]
    dto = HorsePhotosUploadDto(
        files=files,
        names=["Horse Photo 1", "Horse Photo 2"],
        descriptions=["Front view", "Side view"],
    )

    # Act
    result = await horse_service.upload_and_attach_photos(
        test_horse.id,
        dto,
        filenames,
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        user=TEST_ADMIN_USER,
    )

    # Assert
    assert len(result.photos) == 2

    # Проверяем что PhotoService.create вызван с правильными метаданными
    calls = mock_photo_service.create.call_args_list
    assert len(calls) == 2
    assert calls[0][0][0].name == "Horse Photo 1"
    assert calls[0][0][0].description == "Front view"


@pytest.mark.asyncio
async def test_upload_and_attach_photos_photo_service_not_initialized(
    fake_horse_repository: FakeHorseRepository,
    test_horse: Horse,
) -> None:
    """Тест ошибки: PhotoService не инициализирован."""
    # Arrange
    service = HorseService(
        horse_repository=cast(Any, fake_horse_repository),
        horse_children_repository=MagicMock(),
        breed_repository=MagicMock(),
        coat_color_repository=MagicMock(),
        horse_owner_repository=MagicMock(),
        photo_repository=None,
        photo_url_builder=None,
        photo_service=None,
    )

    files = [b"image1"]
    filenames = ["photo1.jpg"]
    dto = HorsePhotosUploadDto(files=files)

    # Act & Assert
    with pytest.raises(ClientError, match="PhotoService не инициализирован"):
        await service.upload_and_attach_photos(
            test_horse.id,
            dto,
            filenames,
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
            user=TEST_ADMIN_USER,
        )
