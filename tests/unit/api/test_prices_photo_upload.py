"""Unit tests for PriceService.upload_and_attach_photos (BE-4)."""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from core.entities.equestrian import EquestrianContext
from core.entities.prices import Price
from core.exceptions.base import ClientError
from core.schemas.photos import (
    PhotoBatchUploadResponseDto,
    PhotoOutShortDto,
)
from core.schemas.prices import PricePhotosUploadDto
from core.services.prices import PriceService
from tests.unit.conftest import (
    TEST_EQUESTRIAN_CONTEXT,
    TEST_EQUESTRIAN_ID,
)


class FakePriceRepository:
    """Fake price repository для изоляции unit tests."""

    def __init__(self) -> None:
        self.prices: dict[UUID, Price] = {}
        self.photo_relations: dict[UUID, list[MagicMock]] = {}

    async def get_by_slug_or_id(
        self, slug_or_id: str | UUID, *, equestrian_id: UUID
    ) -> Price | None:
        """Получить price по slug или id."""
        if isinstance(slug_or_id, UUID):
            price = self.prices.get(slug_or_id)
        else:
            # Поиск по slug
            price = next(
                (p for p in self.prices.values() if p.slug == slug_or_id), None
            )

        if price and price.equestrian_id == equestrian_id:
            return price
        return None

    async def get_price_photos(
        self, price_id: UUID, *, equestrian_id: UUID
    ) -> list[MagicMock]:
        """Получить связи price-photo."""
        return self.photo_relations.get(price_id, [])

    async def set_price_photos(
        self,
        price_id: UUID,
        *,
        photo_ids: list[UUID],
        main_photo_id: UUID | None = None,
        equestrian_id: UUID,
    ) -> None:
        """Установить список фото для price."""
        # Создаём новые связи из photo_ids
        self.photo_relations[price_id] = []
        for photo_id in photo_ids:
            relation = MagicMock()
            relation.photo_id = photo_id
            relation.is_main = photo_id == main_photo_id
            self.photo_relations[price_id].append(relation)


class FakePriceGroupRepository:
    """Fake price group repository."""

    pass


@pytest.fixture
def fake_price_repository() -> FakePriceRepository:
    """Создать fake price repository."""
    return FakePriceRepository()


@pytest.fixture
def fake_price_group_repository() -> FakePriceGroupRepository:
    """Создать fake price group repository."""
    return FakePriceGroupRepository()


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
def price_service(
    fake_price_repository: FakePriceRepository,
    fake_price_group_repository: FakePriceGroupRepository,
    mock_photo_service: AsyncMock,
) -> PriceService:
    """Создать PriceService с fake dependencies."""
    # Mock photo_url_builder to return proper URLs
    photo_url_builder = MagicMock()
    photo_url_builder.build.side_effect = lambda path: f"https://example.com/{path}"

    service = PriceService(
        price_repository=fake_price_repository,
        price_group_repository=fake_price_group_repository,
        photo_repository=MagicMock(),
        photo_url_builder=photo_url_builder,
        photo_service=mock_photo_service,
    )
    return service


@pytest.fixture
def test_price(fake_price_repository: FakePriceRepository) -> Price:
    """Создать тестовую услугу."""
    price = Price(
        id=uuid4(),
        name="Test Price",
        slug="test-price",
        description="Test description",
        page_data="<div>Test</div>",
        equestrian_id=TEST_EQUESTRIAN_ID,
    )
    fake_price_repository.prices[price.id] = price
    return price


@pytest.mark.asyncio
async def test_upload_and_attach_photos_success(
    price_service: PriceService,
    test_price: Price,
    mock_photo_service: AsyncMock,
) -> None:
    """Тест успешной загрузки 3 файлов к услуге."""
    # Arrange
    files = [b"image1", b"image2", b"image3"]
    filenames = ["photo1.jpg", "photo2.jpg", "photo3.jpg"]
    dto = PricePhotosUploadDto(
        files=files,
        names=["Photo 1", "Photo 2", "Photo 3"],
        descriptions=["Desc 1", "Desc 2", "Desc 3"],
    )

    # Act
    result = await price_service.upload_and_attach_photos(
        str(test_price.id),
        dto,
        filenames,
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    # Assert
    assert isinstance(result, PhotoBatchUploadResponseDto)
    assert len(result.photos) == 3
    assert result.errors is None or len(result.errors) == 0

    # Проверяем что PhotoService.create вызван 3 раза
    assert mock_photo_service.create.call_count == 3

    # Проверяем что все фото успешно созданы
    for photo in result.photos:
        assert isinstance(photo, PhotoOutShortDto)
        assert photo.url.startswith("https://")


@pytest.mark.asyncio
async def test_upload_and_attach_photos_partial_success(
    price_service: PriceService,
    test_price: Price,
) -> None:
    """Тест partial success: 2 из 3 файлов успешны."""
    from datetime import datetime, timezone

    from core.entities.photos import Photo

    # Arrange
    files = [b"image1", b"image2", b"image3"]
    filenames = ["photo1.jpg", "photo2.jpg", "photo3.jpg"]
    dto = PricePhotosUploadDto(files=files)

    # Mock PhotoService.create: второй файл вызывает ошибку
    call_count = 0

    async def create_with_error(data, upload, *, equestrian_context):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise ClientError("File too large")

        photo_id = uuid4()
        return Photo(
            id=photo_id,
            name=data.name or upload.filename,
            description=data.description,
            path=f"photos/{photo_id}.jpg",
            equestrian_id=equestrian_context.id,
            created_at=datetime.now(timezone.utc),
        )

    price_service.photo_service.create.side_effect = create_with_error

    # Act
    result = await price_service.upload_and_attach_photos(
        str(test_price.id),
        dto,
        filenames,
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    # Assert
    assert isinstance(result, PhotoBatchUploadResponseDto)
    assert len(result.photos) == 2  # Только 2 успешных
    assert result.errors is not None
    assert len(result.errors) == 1
    assert result.errors[0].index == 1  # Второй файл (index 1)
    assert "File too large" in result.errors[0].message


@pytest.mark.asyncio
async def test_upload_and_attach_photos_full_failure(
    price_service: PriceService,
    test_price: Price,
    mock_photo_service: AsyncMock,
) -> None:
    """Тест полного провала: все файлы с ошибками."""
    # Arrange
    files = [b"image1", b"image2"]
    filenames = ["photo1.jpg", "photo2.jpg"]
    dto = PricePhotosUploadDto(files=files)

    # Mock PhotoService.create: все файлы вызывают ошибку
    mock_photo_service.create.side_effect = ClientError("Invalid image format")

    # Act
    result = await price_service.upload_and_attach_photos(
        str(test_price.id),
        dto,
        filenames,
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    # Assert
    assert isinstance(result, PhotoBatchUploadResponseDto)
    assert len(result.photos) == 0  # Нет успешных
    assert result.errors is not None
    assert len(result.errors) == 2  # Все файлы с ошибками
    assert all("Invalid image format" in e.message for e in result.errors)


@pytest.mark.asyncio
async def test_upload_and_attach_photos_price_not_found(
    price_service: PriceService,
    mock_photo_service: AsyncMock,
) -> None:
    """Тест ошибки: несуществующая услуга (404)."""
    # Arrange
    non_existent_id = uuid4()
    files = [b"image1"]
    filenames = ["photo1.jpg"]
    dto = PricePhotosUploadDto(files=files)

    # Act & Assert
    with pytest.raises(ClientError, match="Цена не найдена"):
        await price_service.upload_and_attach_photos(
            str(non_existent_id),
            dto,
            filenames,
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )

    # Проверяем что PhotoService.create не вызывался
    mock_photo_service.create.assert_not_called()


@pytest.mark.asyncio
async def test_upload_and_attach_photos_with_metadata(
    price_service: PriceService,
    test_price: Price,
    mock_photo_service: AsyncMock,
) -> None:
    """Тест загрузки с метаданными (names и descriptions)."""
    # Arrange
    files = [b"image1", b"image2"]
    filenames = ["photo1.jpg", "photo2.jpg"]
    dto = PricePhotosUploadDto(
        files=files,
        names=["Photo 1", "Photo 2"],
        descriptions=["Description 1", ""],  # Второе описание пустое
    )

    # Act
    result = await price_service.upload_and_attach_photos(
        str(test_price.id),
        dto,
        filenames,
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    # Assert
    assert len(result.photos) == 2

    # Проверяем что PhotoService.create вызван с правильными метаданными
    calls = mock_photo_service.create.call_args_list
    assert len(calls) == 2

    # Первый вызов
    first_call_dto = calls[0][0][0]  # Первый позиционный аргумент (PhotoCreateDto)
    assert first_call_dto.name == "Photo 1"
    assert first_call_dto.description == "Description 1"

    # Второй вызов
    second_call_dto = calls[1][0][0]
    assert second_call_dto.name == "Photo 2"
    assert second_call_dto.description == ""


@pytest.mark.asyncio
async def test_upload_and_attach_photos_mismatched_metadata_length(
    price_service: PriceService,
    test_price: Price,
    mock_photo_service: AsyncMock,
) -> None:
    """Тест несоответствия длины массивов names и files."""
    # Arrange
    files = [b"image1", b"image2", b"image3"]
    filenames = ["photo1.jpg", "photo2.jpg", "photo3.jpg"]
    dto = PricePhotosUploadDto(
        files=files,
        names=["Photo 1", "Photo 2"],  # Только 2 имени для 3 файлов
    )

    # Act
    result = await price_service.upload_and_attach_photos(
        str(test_price.id),
        dto,
        filenames,
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    # Assert
    assert len(result.photos) == 3

    # Проверяем вызовы PhotoService.create
    calls = mock_photo_service.create.call_args_list

    # Первые 2 файла должны иметь указанные names
    assert calls[0][0][0].name == "Photo 1"
    assert calls[1][0][0].name == "Photo 2"

    # Третий файл должен иметь name = None (будет сгенерировано из filename)
    assert calls[2][0][0].name is None


@pytest.mark.asyncio
async def test_upload_and_attach_photos_different_errors(
    price_service: PriceService,
    test_price: Price,
) -> None:
    """Тест partial success с разными ошибками."""
    from datetime import datetime, timezone

    from core.entities.photos import Photo

    # Arrange
    files = [b"image1", b"image2", b"image3", b"image4"]
    filenames = ["photo1.jpg", "photo2.jpg", "photo3.jpg", "photo4.jpg"]
    dto = PricePhotosUploadDto(files=files)

    # Mock PhotoService.create с разными ошибками
    call_count = 0

    async def create_with_varied_errors(data, upload, *, equestrian_context):
        nonlocal call_count
        call_count += 1

        if call_count == 2:
            raise ClientError("File too large")
        elif call_count == 4:
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

    price_service.photo_service.create.side_effect = create_with_varied_errors

    # Act
    result = await price_service.upload_and_attach_photos(
        str(test_price.id),
        dto,
        filenames,
        equestrian_context=TEST_EQUESTRIAN_CONTEXT,
    )

    # Assert
    assert len(result.photos) == 2  # Файлы 0 и 2 успешны
    assert result.errors is not None
    assert len(result.errors) == 2

    # Проверяем индексы и сообщения ошибок
    error_dict = {e.index: e.message for e in result.errors}
    assert 1 in error_dict
    assert "File too large" in error_dict[1]
    assert 3 in error_dict
    assert "Invalid image format" in error_dict[3]


@pytest.mark.asyncio
async def test_upload_and_attach_photos_wrong_tenant(
    price_service: PriceService,
    fake_price_repository: FakePriceRepository,
    mock_photo_service: AsyncMock,
) -> None:
    """Тест попытки загрузить к услуге другого tenant (403)."""
    # Arrange
    other_tenant_id = uuid4()
    other_price = Price(
        id=uuid4(),
        name="Other Price",
        slug="other-price",
        description="Other description",
        page_data="<div>Other</div>",
        equestrian_id=other_tenant_id,
    )
    fake_price_repository.prices[other_price.id] = other_price

    files = [b"image1"]
    filenames = ["photo1.jpg"]
    dto = PricePhotosUploadDto(files=files)

    # Act & Assert - попытка доступа с другим equestrian_context
    with pytest.raises(ClientError, match="Цена не найдена"):
        await price_service.upload_and_attach_photos(
            str(other_price.id),
            dto,
            filenames,
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,  # Другой tenant
        )

    # Проверяем что PhotoService.create не вызывался
    mock_photo_service.create.assert_not_called()


@pytest.mark.asyncio
async def test_upload_and_attach_photos_photo_service_not_initialized(
    fake_price_repository: FakePriceRepository,
    fake_price_group_repository: FakePriceGroupRepository,
    test_price: Price,
) -> None:
    """Тест ошибки: PhotoService не инициализирован."""
    # Arrange
    service = PriceService(
        price_repository=fake_price_repository,
        price_group_repository=fake_price_group_repository,
        photo_repository=MagicMock(),
        photo_url_builder=MagicMock(),
        photo_service=None,  # Явно устанавливаем None
    )

    files = [b"image1"]
    filenames = ["photo1.jpg"]
    dto = PricePhotosUploadDto(files=files)

    # Act & Assert
    with pytest.raises(ClientError, match="PhotoService не инициализирован"):
        await service.upload_and_attach_photos(
            str(test_price.id),
            dto,
            filenames,
            equestrian_context=TEST_EQUESTRIAN_CONTEXT,
        )
